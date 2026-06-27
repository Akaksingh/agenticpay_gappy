"""Enterprise compliance — KYB/AML status and a tamper-evident audit trail (Phase 3).

This is the enterprise upsell surface: businesses running fleets of paying agents
need to prove who an agent is (KYB), that payments were screened (AML), and that
the money trail is auditable and tamper-evident (SOC 2). None of it changes how
payments work — it's a reporting/attestation layer over the same ledger.

The audit log is hash-chained: each entry commits to the previous entry's hash,
so any retroactive edit to history breaks the chain. It's a stand-in for a signed,
append-only audit store; on the Lemma seam this would be backed by Lemma's
datastore with the same chaining.
"""
from __future__ import annotations

import hashlib

from .store import Store

_VALID_KYB = {"verified", "pending", "unverified"}


def set_kyb(store: Store, agent_id: str, status: str) -> dict:
    agent = store.agent(agent_id)
    if agent is None:
        raise ValueError("unknown_agent")
    if status not in _VALID_KYB:
        raise ValueError("invalid_kyb_status")
    agent.kyb_status = status
    return agent.to_public(store.wallet(agent.wallet_id))


def kyb_overview(store: Store) -> dict:
    """KYB/AML posture across the fleet — the compliance dashboard summary."""
    rows = []
    counts = {"verified": 0, "pending": 0, "unverified": 0}
    for a in store.agents.values():
        if a.kind == "platform":
            continue
        counts[a.kyb_status] = counts.get(a.kyb_status, 0) + 1
        rows.append({
            "agent_id": a.id,
            "name": a.name,
            "kyb_status": a.kyb_status,
            # AML screening is "clear" unless KYB is unverified — placeholder logic
            # standing in for a real sanctions/PEP screen at the Lemma seam.
            "aml_screen": "clear" if a.kyb_status != "unverified" else "review_required",
        })
    return {"counts": counts, "agents": rows}


def audit_log(store: Store) -> dict:
    """A hash-chained, append-only view of every settlement event (oldest first)."""
    entries = []
    prev = "0" * 16  # genesis
    for t in store.transactions:
        payload = f"{t.id}|{t.ts}|{t.from_wallet}|{t.to_wallet}|{t.amount}|{t.kind}|{t.status}|{prev}"
        digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
        entries.append({
            "tx_id": t.id,
            "ts": t.ts,
            "kind": t.kind,
            "status": t.status,
            "amount": t.amount,
            "amount_fmt": t.to_public()["amount_fmt"],
            "from_wallet": t.from_wallet,
            "to_wallet": t.to_wallet,
            "reason": t.reason,
            "prev_hash": prev,
            "hash": digest,
        })
        prev = digest
    return {"count": len(entries), "head_hash": prev, "entries": entries}
