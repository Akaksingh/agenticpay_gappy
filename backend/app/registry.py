"""Agent service registry — discover and hire agents by capability (Phase 2).

The network effect: Agent A doesn't need to know Agent B exists, only that it
needs a *capability* ("research", "translate"). The registry returns the
providers that advertise that skill, ranked so the cheapest verified provider
surfaces first. This is the discovery half of the marketplace; escrow (see
`escrow.py`) is the trust half.
"""
from __future__ import annotations

from .store import Store

# Lower KYB rank = more trusted, surfaces higher when price ties.
_KYB_RANK = {"verified": 0, "pending": 1, "unverified": 2}


def find(store: Store, capability: str, max_price: int | None = None) -> list[dict]:
    """Return providers advertising `capability`, ranked by (price, trust)."""
    cap = (capability or "").strip().lower()
    matches = []
    for agent in store.agents.values():
        if agent.kind == "platform" or agent.price_per_call <= 0:
            continue
        skills = [s.lower() for s in agent.skills]
        if cap and cap not in skills:
            continue
        if max_price is not None and agent.price_per_call > max_price:
            continue
        wallet = store.wallet(agent.wallet_id)
        matches.append((agent, wallet))

    matches.sort(key=lambda aw: (aw[0].price_per_call, _KYB_RANK.get(aw[0].kyb_status, 3)))
    return [a.to_public(w) for a, w in matches]


def capabilities(store: Store) -> list[str]:
    """All distinct capabilities currently offered in the marketplace."""
    caps: set[str] = set()
    for agent in store.agents.values():
        if agent.kind != "platform" and agent.price_per_call > 0:
            caps.update(agent.skills)
    return sorted(caps)
