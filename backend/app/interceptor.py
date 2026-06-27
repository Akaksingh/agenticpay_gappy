"""The x402 interceptor — AgentPay's "pay-aware in under an hour" SDK primitive.

A developer wraps their normal request flow in a `PayAwareSession` and never
writes payment code again: any resource that answers `402 Payment Required` is
paid automatically from the agent's wallet — *within its budget* — and the
request is transparently retried with the payment receipt.

The crucial property (the moat): the interceptor never moves money itself. It
calls `x402.pay_challenge`, which goes through `ledger.settle`, where the wallet's
`BudgetPolicy` is enforced. So even a fully compromised client that *wants* to
overspend physically cannot — the ceiling lives at the protocol level, below the
SDK. `auto_pay_ceiling` is a courtesy client-side guard on top of that, not the
thing that makes it safe.

`fetch` is any callable `(headers: dict) -> (status_code: int, body: dict)`. In
this app it wraps the in-process service handler; against a real network it would
wrap `httpx`/`requests`. Either way the interceptor logic is identical.
"""
from __future__ import annotations

from typing import Callable

from .ledger import PaymentError
from .models import fmt_usdc
from .store import Store
from .x402 import pay_challenge

Fetch = Callable[[dict], "tuple[int, dict]"]


class PayAwareSession:
    def __init__(self, store: Store, wallet_id: str, auto_pay_ceiling: int | None = None) -> None:
        self.store = store
        self.wallet_id = wallet_id
        self.auto_pay_ceiling = auto_pay_ceiling  # optional client-side max micros per call
        self.trace: list[dict] = []

    def get(self, fetch: Fetch) -> dict:
        """Run a request, transparently paying a single 402 challenge if one is raised."""
        status, body = fetch({})
        if status != 402:
            self.trace.append({"step": "ok_no_payment", "detail": "Resource was free", "status": status})
            return {"ok": True, "status": status, "result": body, "trace": self.trace, "paid": 0}

        accept = (body.get("accepts") or [{}])[0]
        amount = accept.get("maxAmountRequired", 0)
        self.trace.append({
            "step": "payment_required",
            "label": "402 intercepted",
            "detail": f"SDK caught 402 for {fmt_usdc(amount)} — auto-paying",
            "amount": amount,
        })

        # Courtesy client-side ceiling (the hard limit is enforced in the ledger below).
        if self.auto_pay_ceiling is not None and amount > self.auto_pay_ceiling:
            self.trace.append({
                "step": "payment_blocked",
                "detail": f"Above client auto-pay ceiling {fmt_usdc(self.auto_pay_ceiling)}",
                "reason": "above_auto_pay_ceiling",
            })
            return {"ok": False, "reason": "above_auto_pay_ceiling", "trace": self.trace, "paid": 0}

        try:
            receipt_id, tx = pay_challenge(self.store, accept["nonce"], self.wallet_id)
        except PaymentError as e:
            # Budget enforcement fired inside the ledger — the interceptor cannot override it.
            self.trace.append({
                "step": "payment_blocked",
                "detail": f"Budget policy blocked auto-pay: {e.reason}",
                "reason": e.reason,
            })
            return {"ok": False, "reason": e.reason, "trace": self.trace, "paid": 0}

        self.trace.append({
            "step": "payment_settled",
            "detail": f"Auto-paid {fmt_usdc(amount)} · receipt {receipt_id}",
            "tx": tx.id,
        })

        # Retry transparently with the receipt attached.
        status, body = fetch({"X-PAYMENT": receipt_id})
        self.trace.append({
            "step": "work_delivered",
            "detail": f"Retried with receipt → {status}",
        })
        return {"ok": status == 200, "status": status, "result": body,
                "trace": self.trace, "paid": amount, "receipt": receipt_id, "tx": tx.id}
