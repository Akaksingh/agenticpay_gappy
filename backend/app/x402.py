"""A simulated x402 ("HTTP 402 Payment Required") flow.

The real x402 protocol works like this:
  1. Client requests a priced resource with no payment.
  2. Server replies `402` with a JSON body describing what to pay and to whom.
  3. Client constructs a payment and retries with an `X-PAYMENT` header.
  4. Server verifies the payment and serves the resource.

We keep that exact handshake but settle against the in-memory stablecoin ledger
instead of a chain, so the demo is protocol-accurate and stage-safe. Swapping in
a real chain later means changing only `pay_challenge`.
"""
from __future__ import annotations

from .ledger import settle
from .models import fmt_usdc, new_id
from .store import Store

NETWORK = "lemma-sim"  # would be e.g. "base-sepolia" on a real testnet


def make_challenge(
    store: Store, resource: str, pay_to_wallet: str, amount: int, description: str
) -> dict:
    """Build the 402 body and remember the nonce so we can verify the payment."""
    nonce = new_id("ch")
    store.challenges[nonce] = {
        "resource": resource,
        "pay_to": pay_to_wallet,
        "amount": amount,
        "description": description,
    }
    return {
        "x402Version": 1,
        "error": "payment_required",
        "accepts": [
            {
                "scheme": "exact",
                "network": NETWORK,
                "asset": "USDC",
                "maxAmountRequired": amount,
                "amountFormatted": fmt_usdc(amount),
                "payTo": pay_to_wallet,
                "resource": resource,
                "nonce": nonce,
                "description": description,
            }
        ],
    }


def pay_challenge(store: Store, nonce: str, from_wallet: str):
    """Pay a 402 challenge from `from_wallet`; returns (receipt_id, transaction)."""
    ch = store.challenges.get(nonce)
    if ch is None:
        from .ledger import PaymentError

        raise PaymentError("unknown_challenge")
    tx = settle(
        store,
        from_wallet,
        ch["pay_to"],
        ch["amount"],
        kind="micropayment",
        memo=f"x402 · {ch['description']}",
        ref=nonce,
    )
    receipt_id = new_id("rcpt")
    store.receipts[receipt_id] = {
        "nonce": nonce,
        "resource": ch["resource"],
        "tx": tx.id,
        "payer": from_wallet,
    }
    return receipt_id, tx


def verify_receipt(store: Store, receipt_id: str, resource: str) -> dict | None:
    """Confirm a receipt exists and was issued for exactly this resource."""
    r = store.receipts.get(receipt_id)
    if r is None or r["resource"] != resource:
        return None
    return r
