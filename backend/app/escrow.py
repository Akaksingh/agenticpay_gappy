"""Escrowed, outcome-based payments — the trust primitive of the marketplace (Phase 2).

When Agent A hires an unfamiliar Agent B, neither wants to go first. AgentPay
solves it by holding the payment in a platform Vault: funds leave the client's
wallet up front (so the provider knows they're good), but only reach the provider
once the work is accepted. If the outcome fails, the hold is refunded.

Every leg runs through `ledger.settle`, so the *hold itself is budget-enforced* —
an agent can't escrow more than its policy allows, and the take rate is collected
on release, exactly like a direct settlement.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ledger import PaymentError, settle
from .models import fmt_usdc, new_id, now_ms
from .store import Store


@dataclass
class Escrow:
    id: str
    ts: int
    client_id: str
    provider_id: str
    amount: int
    status: str            # 'held' | 'released' | 'refunded'
    memo: str
    hold_tx: str | None = None
    settle_tx: str | None = None
    outcome: str | None = None  # free-text reason on release/refund

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "ts": self.ts,
            "client_id": self.client_id,
            "provider_id": self.provider_id,
            "amount": self.amount,
            "amount_fmt": fmt_usdc(self.amount),
            "status": self.status,
            "memo": self.memo,
            "hold_tx": self.hold_tx,
            "settle_tx": self.settle_tx,
            "outcome": self.outcome,
        }


def open_escrow(store: Store, client_id: str, provider_id: str, amount: int, memo: str = "") -> Escrow:
    """Move `amount` from the client into the Vault and record a held escrow.

    Budget policy is enforced here (the hold is a real outgoing payment), so a
    client cannot escrow beyond its per-call / daily limits.
    """
    client = store.agent(client_id)
    provider = store.agent(provider_id)
    if client is None or provider is None:
        raise PaymentError("unknown_agent")
    if store.vault_wallet_id is None:
        raise PaymentError("vault_unavailable")

    esc = Escrow(
        id=new_id("esc"), ts=now_ms(), client_id=client_id, provider_id=provider_id,
        amount=amount, status="held", memo=memo or f"Escrow: {client.name} → {provider.name}",
    )
    hold = settle(
        store, client.wallet_id, store.vault_wallet_id, amount,
        kind="escrow_hold", memo=esc.memo, ref=esc.id,
    )
    esc.hold_tx = hold.id
    store.escrows[esc.id] = esc
    return esc


def release(store: Store, escrow_id: str, outcome: str = "accepted") -> Escrow:
    """Release a held escrow to the provider (the take rate applies on settlement)."""
    esc = _held(store, escrow_id)
    provider = store.agent(esc.provider_id)
    tx = settle(
        store, store.vault_wallet_id, provider.wallet_id, esc.amount,
        kind="escrow_release", memo=f"Escrow release · {outcome}", ref=esc.id,
    )
    esc.status, esc.settle_tx, esc.outcome = "released", tx.id, outcome
    return esc


def refund(store: Store, escrow_id: str, outcome: str = "rejected") -> Escrow:
    """Refund a held escrow back to the client (no take rate on a refund)."""
    esc = _held(store, escrow_id)
    client = store.agent(esc.client_id)
    tx = settle(
        store, store.vault_wallet_id, client.wallet_id, esc.amount,
        kind="refund", memo=f"Escrow refund · {outcome}", ref=esc.id,
    )
    esc.status, esc.settle_tx, esc.outcome = "refunded", tx.id, outcome
    return esc


def _held(store: Store, escrow_id: str) -> Escrow:
    esc = store.escrows.get(escrow_id)
    if esc is None:
        raise PaymentError("unknown_escrow")
    if esc.status != "held":
        raise PaymentError(f"escrow_not_held:{esc.status}")
    return esc
