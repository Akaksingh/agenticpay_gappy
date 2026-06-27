"""Demo data: a small economy of agents that pay each other."""
from __future__ import annotations

from .ledger import topup
from .models import USDC, Agent, BudgetPolicy, Wallet, new_id
from .store import Store


def _make(store: Store, name, kind, avatar, skills, price, balance, per_call, daily, kyb="verified"):
    wallet_id = new_id("w")
    agent = Agent(
        id=new_id("agt"),
        name=name,
        kind=kind,
        wallet_id=wallet_id,
        avatar=avatar,
        skills=skills,
        price_per_call=price,
        kyb_status=kyb,
    )
    wallet = Wallet(
        id=wallet_id,
        agent_id=agent.id,
        balance=0,
        policy=BudgetPolicy(per_call_limit=per_call, daily_limit=daily),
    )
    store.add_agent(agent, wallet)
    if balance:
        topup(store, wallet_id, balance, memo="Initial funding")
    return agent


def seed(store: Store) -> None:
    store.clear()
    # The orchestrator: holds a real budget and hires others.
    _make(
        store, "Atlas", "orchestrator", "🧭",
        skills=["planning"], price=0,
        balance=50 * USDC, per_call=2 * USDC, daily=20 * USDC,
    )
    # Worker / service agents that charge per call.
    _make(
        store, "Sage", "worker", "🔬",
        skills=["research"], price=int(0.75 * USDC),
        balance=2 * USDC, per_call=1 * USDC, daily=10 * USDC,
    )
    _make(
        store, "Lingo", "worker", "🌐",
        skills=["translate"], price=int(0.25 * USDC),
        balance=1 * USDC, per_call=1 * USDC, daily=10 * USDC,
    )
    _make(
        store, "Quill", "worker", "✍️",
        skills=["summarize"], price=int(0.40 * USDC),
        balance=1 * USDC, per_call=1 * USDC, daily=10 * USDC,
    )
    _make(
        store, "Ticker", "service", "📈",
        skills=["market-data"], price=int(0.10 * USDC),
        balance=1 * USDC, per_call=1 * USDC, daily=10 * USDC,
    )
    # A second research provider so the registry has real competition to rank.
    # Cheaper than Sage, but KYB still pending — discovery surfaces both signals.
    _make(
        store, "Orion", "worker", "🛰️",
        skills=["research", "summarize"], price=int(0.50 * USDC),
        balance=1 * USDC, per_call=1 * USDC, daily=10 * USDC,
        kyb="pending",
    )

    # --- platform wallets (Lemma seam) -----------------------------------
    # Treasury collects the take rate; Vault custodies escrowed funds. Both get
    # permissive policies because they move platform money, not an agent's budget.
    big = 1_000_000 * USDC
    treasury = _make(
        store, "Treasury", "platform", "🏦",
        skills=[], price=0, balance=0, per_call=big, daily=big,
    )
    vault = _make(
        store, "Escrow Vault", "platform", "🔒",
        skills=[], price=0, balance=0, per_call=big, daily=big,
    )
    store.treasury_wallet_id = treasury.wallet_id
    store.vault_wallet_id = vault.wallet_id
