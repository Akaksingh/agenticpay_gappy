"""The ledger: atomic transfers with programmable-budget enforcement.

Every wallet-to-wallet payment runs through `settle`, which checks the payer's
`BudgetPolicy` (per-call cap, daily cap, allow-listed payees) and balance
*before* moving any money. Rejections are recorded too, so the dashboard can
show "this payment was blocked by the agent's budget" — which is the whole
point of programmable money for agents.
"""
from __future__ import annotations

import logging

from .lemma_sdk import LemmaNotWired
from .lemma_sdk import client as lemma_client
from .models import (
    TAKE_RATE_BPS,
    Transaction,
    day_bucket,
    fmt_usdc,
    new_id,
    now_ms,
    take_rate_fee,
)
from .store import Store

log = logging.getLogger("agentpay.ledger")

# Payment kinds that earn the platform take rate (settlement volume).
REVENUE_KINDS = {"micropayment", "settlement", "escrow_release"}


def _mirror(tx: Transaction) -> None:
    """Best-effort: record a settled ledger event as a Lemma settlement event.

    This is the "every AgentPay transaction maps to a Lemma settlement" contract,
    enforced at the ledger (protocol) seam. It's fire-and-forget: if Lemma isn't
    wired or errors, the local ledger remains the source of truth.
    """
    if not lemma_client.available or tx.status != "settled":
        return
    try:
        lemma_client.mirror_settlement(
            tx_id=tx.id, from_ref=tx.from_wallet, to_ref=tx.to_wallet,
            amount=tx.amount, kind=tx.kind, memo=tx.memo,
        )
    except LemmaNotWired:
        pass  # expected until settlement mapping is filled in from the SDK docs
    except Exception as e:  # noqa: BLE001 — mirroring must never break a payment
        log.warning("Lemma settlement mirror failed for %s (%s).", tx.id, e)


class PaymentError(Exception):
    def __init__(self, reason: str, tx: Transaction | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.tx = tx


def _roll_daily_bucket(policy, ts: int) -> None:
    bucket = day_bucket(ts)
    if policy.day != bucket:
        policy.day = bucket
        policy.spent_today = 0


def topup(store: Store, wallet_id: str, amount: int, memo: str = "Faucet top-up") -> Transaction:
    """Mint funds into a wallet (the demo faucet)."""
    w = store.wallet(wallet_id)
    if w is None:
        raise PaymentError("unknown_wallet")
    if amount <= 0:
        raise PaymentError("invalid_amount")
    w.balance += amount
    tx = Transaction(new_id("tx"), now_ms(), None, wallet_id, amount, "topup", memo, "settled")
    store.record(tx)
    _mirror(tx)
    return tx


def settle(
    store: Store,
    from_wallet: str,
    to_wallet: str,
    amount: int,
    kind: str,
    memo: str,
    ref: str | None = None,
) -> Transaction:
    """Move `amount` micros from one wallet to another, enforcing the payer's policy."""
    ts = now_ms()
    src = store.wallet(from_wallet)
    dst = store.wallet(to_wallet)
    if src is None:
        raise PaymentError("unknown_source_wallet")
    if dst is None:
        raise PaymentError("unknown_payee_wallet")
    if amount <= 0:
        raise PaymentError("invalid_amount")
    if from_wallet == to_wallet:
        raise PaymentError("self_payment")

    policy = src.policy
    _roll_daily_bucket(policy, ts)

    reason: str | None = None
    if amount > policy.per_call_limit:
        reason = "exceeds_per_call_limit"
    elif policy.spent_today + amount > policy.daily_limit:
        reason = "exceeds_daily_limit"
    elif policy.allowed_payees and dst.id not in policy.allowed_payees:
        reason = "payee_not_allowed"
    elif src.balance < amount:
        reason = "insufficient_balance"

    if reason is not None:
        tx = Transaction(
            new_id("tx"), ts, from_wallet, to_wallet, amount, kind, memo, "rejected", ref, reason
        )
        store.record(tx)
        raise PaymentError(reason, tx)

    # All checks passed — perform the atomic transfer.
    src.balance -= amount
    dst.balance += amount
    policy.spent_today += amount
    tx = Transaction(new_id("tx"), ts, from_wallet, to_wallet, amount, kind, memo, "settled", ref)
    store.record(tx)
    _mirror(tx)
    _skim_take_rate(store, dst, amount, kind, ref)
    return tx


def _skim_take_rate(store: Store, payee, amount: int, kind: str, ref: str | None) -> None:
    """Skim the platform take rate from a settled payment into the treasury.

    This is AgentPay's revenue model: 0.5% of settlement volume. The fee is taken
    from the *payee* so the payer's budget math is unchanged — a payer is charged
    exactly the price it agreed to, and the provider nets price - fee. The fee
    moves at the ledger (protocol) level, not in application code, so no agent can
    route around it.
    """
    treasury_id = store.treasury_wallet_id
    if treasury_id is None or kind not in REVENUE_KINDS or payee.id == treasury_id:
        return
    fee = take_rate_fee(amount)
    if fee <= 0 or payee.balance < fee:
        return
    treasury = store.wallet(treasury_id)
    payee.balance -= fee
    treasury.balance += fee
    fee_tx = Transaction(
        new_id("tx"), now_ms(), payee.id, treasury_id, fee, "fee",
        f"Platform take rate {TAKE_RATE_BPS / 100:.2f}%", "settled", ref,
    )
    store.record(fee_tx)
    _mirror(fee_tx)


def stats(store: Store) -> dict:
    settled = [t for t in store.transactions if t.status == "settled" and t.kind in REVENUE_KINDS]
    rejected = [t for t in store.transactions if t.status == "rejected"]
    fees = [t for t in store.transactions if t.status == "settled" and t.kind == "fee"]
    volume = sum(t.amount for t in settled)
    revenue = sum(t.amount for t in fees)
    # Count user-facing agents only — platform wallets (treasury/vault) aren't "agents".
    agents = sum(1 for a in store.agents.values() if a.kind != "platform")
    return {
        "total_payments": len(settled),
        "total_volume": volume,
        "total_volume_fmt": fmt_usdc(volume),
        "rejected": len(rejected),
        "agents": agents,
        "take_rate_bps": TAKE_RATE_BPS,
        "platform_revenue": revenue,
        "platform_revenue_fmt": fmt_usdc(revenue),
    }
