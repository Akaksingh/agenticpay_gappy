"""Domain models for AgentPay.

Money is stored as integer **micro-USDC** (1 USDC = 1_000_000 micros) so the
ledger never touches floats. Everything user-facing is formatted via `fmt_usdc`.
"""
from __future__ import annotations

import datetime
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

USDC = 1_000_000  # micro-units per 1 USDC

# Platform take rate on settlement volume, in basis points (50 bps = 0.5%).
# This is the revenue model: a thin skim on every settled payment.
TAKE_RATE_BPS = 50


def take_rate_fee(amount: int) -> int:
    """Platform fee (micros) charged on a settled payment of `amount` micros."""
    return amount * TAKE_RATE_BPS // 10_000


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def now_ms() -> int:
    return int(time.time() * 1000)


def day_bucket(ts_ms: int) -> str:
    return datetime.datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d")


def fmt_usdc(micros: int) -> str:
    return f"{micros / USDC:,.4f} USDC"


@dataclass
class BudgetPolicy:
    """Programmable spending rules enforced on every outgoing payment."""

    per_call_limit: int          # max micros for a single payment
    daily_limit: int             # max micros spent per UTC day
    allowed_payees: list[str] = field(default_factory=list)  # wallet ids; empty = allow any
    spent_today: int = 0
    day: str = ""                # UTC day bucket the spent_today counter belongs to

    def to_public(self) -> dict:
        return {
            "per_call_limit": self.per_call_limit,
            "per_call_limit_fmt": fmt_usdc(self.per_call_limit),
            "daily_limit": self.daily_limit,
            "daily_limit_fmt": fmt_usdc(self.daily_limit),
            "allowed_payees": self.allowed_payees,
            "spent_today": self.spent_today,
            "spent_today_fmt": fmt_usdc(self.spent_today),
            "daily_remaining": max(0, self.daily_limit - self.spent_today),
        }


@dataclass
class Wallet:
    id: str
    agent_id: str
    balance: int                 # micros
    policy: BudgetPolicy

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "balance": self.balance,
            "balance_fmt": fmt_usdc(self.balance),
            "policy": self.policy.to_public(),
        }


@dataclass
class Agent:
    id: str
    name: str
    kind: str                    # 'orchestrator' | 'worker' | 'service' | 'platform'
    wallet_id: str
    avatar: str = "🤖"
    skills: list[str] = field(default_factory=list)
    price_per_call: int = 0      # micros charged when this agent is invoked (workers/services)
    kyb_status: str = "verified" # 'verified' | 'pending' | 'unverified'  (Phase 3 compliance)

    def to_public(self, wallet: Wallet) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "avatar": self.avatar,
            "skills": self.skills,
            "price_per_call": self.price_per_call,
            "price_per_call_fmt": fmt_usdc(self.price_per_call),
            "kyb_status": self.kyb_status,
            "wallet": wallet.to_public(),
        }


@dataclass
class Transaction:
    id: str
    ts: int
    from_wallet: Optional[str]
    to_wallet: Optional[str]
    amount: int
    kind: str                    # topup | micropayment | settlement | escrow_hold | escrow_release | refund | fee
    memo: str
    status: str                  # 'settled' | 'rejected'
    ref: Optional[str] = None    # x402 nonce / task id
    reason: Optional[str] = None # rejection reason

    def to_public(self) -> dict:
        return {
            "id": self.id,
            "ts": self.ts,
            "from_wallet": self.from_wallet,
            "to_wallet": self.to_wallet,
            "amount": self.amount,
            "amount_fmt": fmt_usdc(self.amount),
            "kind": self.kind,
            "memo": self.memo,
            "status": self.status,
            "ref": self.ref,
            "reason": self.reason,
        }
