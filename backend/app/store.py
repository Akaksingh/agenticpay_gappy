"""In-memory datastore.

This is the **Lemma datastore seam**: every read/write of agents, wallets,
transactions, x402 challenges and receipts goes through `Store`. When the
hackathon Lemma SDK is wired in (see `lemma_adapter.py`), this class is the one
thing that gets reimplemented on top of Lemma datastores — the rest of the app
never touches raw storage.
"""
from __future__ import annotations

from .models import Agent, Transaction, Wallet


class Store:
    def __init__(self) -> None:
        self.agents: dict[str, Agent] = {}
        self.wallets: dict[str, Wallet] = {}
        self.transactions: list[Transaction] = []
        self.challenges: dict[str, dict] = {}  # nonce -> {resource, pay_to, amount, description}
        self.receipts: dict[str, dict] = {}    # receipt_id -> {nonce, resource, tx, payer}
        self.escrows: dict[str, object] = {}   # escrow_id -> Escrow (Phase 2 outcome-based payments)
        # Platform wallets (set during seed): the treasury collects the take rate,
        # the vault custodies escrowed funds. Both are part of the Lemma seam.
        self.treasury_wallet_id: str | None = None
        self.vault_wallet_id: str | None = None

    # --- agents / wallets -------------------------------------------------
    def add_agent(self, agent: Agent, wallet: Wallet) -> None:
        self.agents[agent.id] = agent
        self.wallets[wallet.id] = wallet

    def agent(self, agent_id: str) -> Agent | None:
        return self.agents.get(agent_id)

    def wallet(self, wallet_id: str) -> Wallet | None:
        return self.wallets.get(wallet_id)

    def wallet_for_agent(self, agent_id: str) -> Wallet | None:
        a = self.agents.get(agent_id)
        return self.wallets.get(a.wallet_id) if a else None

    # --- ledger -----------------------------------------------------------
    def record(self, tx: Transaction) -> Transaction:
        self.transactions.append(tx)
        return tx

    def ledger(self, limit: int = 100) -> list[Transaction]:
        return list(reversed(self.transactions[-limit:]))

    def clear(self) -> None:
        self.agents.clear()
        self.wallets.clear()
        self.transactions.clear()
        self.challenges.clear()
        self.receipts.clear()
        self.escrows.clear()
        self.treasury_wallet_id = None
        self.vault_wallet_id = None
