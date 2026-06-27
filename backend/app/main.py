"""AgentPay API — payment rails for AI agents.

Endpoints
  GET  /v1/agents                       list agents + wallets + budgets
  GET  /v1/transactions                 ledger feed (newest first)
  GET  /v1/stats                        dashboard totals
  POST /v1/wallets/{id}/topup           faucet a wallet
  PUT  /v1/wallets/{id}/policy          update programmable budget
  GET  /v1/services/{agent_id}/invoke   raw x402: 402 challenge or, with X-PAYMENT, the result
  POST /v1/pay                          pay an x402 challenge -> receipt
  POST /v1/autopay                      x402 interceptor: transparent auto-pay + retry (Phase 1)
  POST /v1/hire                         one-click: client agent hires provider (full handshake + trace)
  GET  /v1/registry                     discover providers by capability (Phase 2)
  POST /v1/hire/escrow                  outcome-based hire via escrow (Phase 2)
  GET  /v1/escrow                       list escrows
  POST /v1/escrow/{id}/release          release a held escrow to the provider
  POST /v1/escrow/{id}/refund           refund a held escrow to the client
  GET  /v1/compliance/agents            KYB/AML posture across the fleet (Phase 3)
  POST /v1/agents/{id}/kyb              set an agent's KYB status
  GET  /v1/compliance/audit             hash-chained, tamper-evident audit trail (Phase 3)
  POST /v1/demo/scenario                scripted multi-step demo
  POST /v1/demo/reset                   reseed the economy
  GET  /v1/health                       liveness + active settlement backend (memory|lemma)
"""
from __future__ import annotations

from fastapi import FastAPI, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import logging

from . import compliance, escrow, registry
from .config import settings
from .ledger import PaymentError, stats, topup
from .lemma_adapter import LemmaAdapter
from .lemma_sdk import client as lemma_client
from .seed import seed
from .store import Store
from .x402 import make_challenge, pay_challenge, verify_receipt

logging.basicConfig(level=logging.INFO)
logging.getLogger("agentpay").info(
    "AgentPay starting — backend=%s, lemma_available=%s (%s)",
    settings.backend, lemma_client.available, lemma_client.status()["detail"],
)

app = FastAPI(title="AgentPay", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

store = Store()
lemma = LemmaAdapter(store)
seed(store)


# --- helpers -------------------------------------------------------------
def _agent_public(agent):
    return agent.to_public(store.wallet(agent.wallet_id))


def _err(reason: str, code: int = 400):
    return Response(content=f'{{"error":"{reason}"}}', media_type="application/json", status_code=code)


# --- read endpoints ------------------------------------------------------
@app.get("/v1/agents")
def list_agents():
    return {"agents": [_agent_public(a) for a in store.agents.values()]}


@app.get("/v1/transactions")
def list_transactions(limit: int = 100):
    return {"transactions": [t.to_public() for t in store.ledger(limit)]}


@app.get("/v1/stats")
def get_stats():
    return stats(store)


# --- wallet management ---------------------------------------------------
class TopupBody(BaseModel):
    amount_usdc: float = 10.0


@app.post("/v1/wallets/{wallet_id}/topup")
def wallet_topup(wallet_id: str, body: TopupBody):
    try:
        tx = topup(store, wallet_id, int(body.amount_usdc * 1_000_000))
    except PaymentError as e:
        return _err(e.reason, 404)
    return {"ok": True, "transaction": tx.to_public()}


class PolicyBody(BaseModel):
    per_call_usdc: float | None = None
    daily_usdc: float | None = None
    allowed_payees: list[str] | None = None


@app.put("/v1/wallets/{wallet_id}/policy")
def update_policy(wallet_id: str, body: PolicyBody):
    w = store.wallet(wallet_id)
    if w is None:
        return _err("unknown_wallet", 404)
    if body.per_call_usdc is not None:
        w.policy.per_call_limit = int(body.per_call_usdc * 1_000_000)
    if body.daily_usdc is not None:
        w.policy.daily_limit = int(body.daily_usdc * 1_000_000)
    if body.allowed_payees is not None:
        w.policy.allowed_payees = body.allowed_payees
    return {"ok": True, "wallet": w.to_public()}


# --- raw x402 handshake (inspectable) ------------------------------------
@app.get("/v1/services/{agent_id}/invoke")
def invoke_service(agent_id: str, input: str = "", x_payment: str | None = Header(default=None)):
    agent = store.agent(agent_id)
    if agent is None:
        return _err("unknown_agent", 404)
    resource = f"agent://{agent.id}/invoke"

    if x_payment is None:
        challenge = make_challenge(
            store, resource, agent.wallet_id, agent.price_per_call,
            description=f"{agent.name} · {', '.join(agent.skills) or 'work'}",
        )
        return Response(
            content=__import__("json").dumps(challenge),
            media_type="application/json",
            status_code=402,
        )

    if verify_receipt(store, x_payment, resource) is None:
        return _err("invalid_or_missing_payment", 402)
    return {"ok": True, "result": lemma.run_agent(agent, input)}


class PayBody(BaseModel):
    nonce: str
    from_wallet: str


@app.post("/v1/pay")
def pay(body: PayBody):
    try:
        receipt_id, tx = pay_challenge(store, body.nonce, body.from_wallet)
    except PaymentError as e:
        return _err(e.reason, 402)
    return {"ok": True, "receipt": receipt_id, "transaction": tx.to_public()}


# --- one-click hire (full handshake + trace) -----------------------------
class HireBody(BaseModel):
    client_id: str
    provider_id: str
    input: str = ""


@app.post("/v1/hire")
def hire(body: HireBody):
    try:
        return lemma.hire(body.client_id, body.provider_id, body.input)
    except PaymentError as e:
        return _err(e.reason, 400)


# --- x402 interceptor (Phase 1: transparent auto-pay) --------------------
@app.post("/v1/autopay")
def autopay(body: HireBody):
    """Drive the provider's priced resource through the PayAwareSession SDK.

    Same money movement as /v1/hire, but the trace shows the *interceptor* catching
    the 402 and auto-paying — the "make an agent pay-aware in under an hour" story.
    """
    try:
        return lemma.autopay(body.client_id, body.provider_id, body.input)
    except PaymentError as e:
        return _err(e.reason, 400)


# --- agent registry (Phase 2: discovery) ---------------------------------
@app.get("/v1/registry")
def discover(capability: str = "", max_price_usdc: float | None = None):
    max_price = int(max_price_usdc * 1_000_000) if max_price_usdc is not None else None
    return {
        "capability": capability,
        "capabilities": registry.capabilities(store),
        "providers": registry.find(store, capability, max_price),
    }


# --- escrowed outcome-based payment (Phase 2: trust) ---------------------
class EscrowHireBody(BaseModel):
    client_id: str
    provider_id: str
    input: str = ""
    simulate_outcome: str = "success"  # 'success' -> release, 'failure' -> refund


@app.post("/v1/hire/escrow")
def hire_escrow(body: EscrowHireBody):
    try:
        return lemma.hire_with_escrow(
            body.client_id, body.provider_id, body.input, body.simulate_outcome
        )
    except PaymentError as e:
        return _err(e.reason, 400)


@app.get("/v1/escrow")
def list_escrows():
    return {"escrows": [e.to_public() for e in store.escrows.values()]}


@app.post("/v1/escrow/{escrow_id}/release")
def release_escrow(escrow_id: str):
    try:
        return {"ok": True, "escrow": escrow.release(store, escrow_id).to_public()}
    except PaymentError as e:
        return _err(e.reason, 400)


@app.post("/v1/escrow/{escrow_id}/refund")
def refund_escrow(escrow_id: str):
    try:
        return {"ok": True, "escrow": escrow.refund(store, escrow_id).to_public()}
    except PaymentError as e:
        return _err(e.reason, 400)


# --- enterprise compliance (Phase 3) -------------------------------------
@app.get("/v1/compliance/agents")
def compliance_agents():
    return compliance.kyb_overview(store)


class KybBody(BaseModel):
    status: str  # 'verified' | 'pending' | 'unverified'


@app.post("/v1/agents/{agent_id}/kyb")
def set_kyb(agent_id: str, body: KybBody):
    try:
        return {"ok": True, "agent": compliance.set_kyb(store, agent_id, body.status)}
    except ValueError as e:
        return _err(str(e), 400)


@app.get("/v1/compliance/audit")
def compliance_audit():
    return compliance.audit_log(store)


# --- scripted demo -------------------------------------------------------
@app.post("/v1/demo/scenario")
def run_scenario():
    """Atlas runs a multi-agent job touching every rail: discovery, the x402
    interceptor, a direct hire, escrow (released + refunded), and a budget block."""
    atlas = next(a for a in store.agents.values() if a.name == "Atlas")
    by_name = {a.name: a for a in store.agents.values()}
    results = []

    # Phase 2 discovery: find the cheapest research provider, then auto-pay it (Phase 1 interceptor).
    research = registry.find(store, "research")
    if research:
        results.append(lemma.autopay(atlas.id, research[0]["id"], "stablecoin payments for AI agents"))

    # A live market-data quote via the interceptor.
    results.append(lemma.autopay(atlas.id, by_name["Ticker"].id, "ETH"))

    # Escrowed outcome-based hires: one accepted (released), one rejected (refunded).
    results.append(lemma.hire_with_escrow(
        atlas.id, by_name["Quill"].id,
        "Agentic commerce lets agents pay per API call without a human in the loop.", "success"))
    results.append(lemma.hire_with_escrow(atlas.id, by_name["Lingo"].id, "hello agent economy", "failure"))

    # Budget enforcement at the protocol level: tighten Atlas's per-call cap, watch
    # the next payment get blocked by the ledger, then restore the cap.
    saved = store.wallet(atlas.wallet_id).policy.per_call_limit
    store.wallet(atlas.wallet_id).policy.per_call_limit = 50_000  # 0.05 USDC
    results.append(lemma.autopay(atlas.id, by_name["Sage"].id, "this should be blocked"))
    store.wallet(atlas.wallet_id).policy.per_call_limit = saved

    return {"results": results}


@app.post("/v1/demo/reset")
def reset():
    seed(store)
    return {"ok": True, "agents": len(store.agents)}


@app.get("/")
def root():
    return {
        "service": "AgentPay",
        "docs": "/docs",
        "agents": sum(1 for a in store.agents.values() if a.kind != "platform"),
        "backend": settings.backend,
        "lemma_available": lemma_client.available,
    }


@app.get("/v1/health")
def health():
    """Liveness + which settlement backend is active (in-memory vs. real Lemma)."""
    return {"ok": True, **lemma_client.status()}
