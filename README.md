# AgentPay — Payment Rails for AI Agents

> Stripe for AI agents. A wallet + payment protocol where an AI agent has a
> **programmable budget**, **per-call spending limits**, and can **pay per API
> call in stablecoins** (x402 micropayments). One agent hires another → settles
> instantly.

Built for the **Lemma SDK hackathon** (India's first, powered by Lemma SDK).

---

## Why this matters

AI agents can't hold money or pay each other. As agents start doing real
work — calling APIs, buying data, hiring other agents — they need money that is
**programmable and bounded**, not a human's credit card. AgentPay gives every
agent a wallet with rules the agent *cannot* exceed, and a real
`HTTP 402 Payment Required` micropayment flow for pay-per-call.

## What's in the demo

Built across the three phases of the product roadmap:

**Phase 1 — the atomic primitive (give every agent a bounded wallet)**
- **Agent wallets & budgets** — balance, per-call cap, daily cap, allow-listed
  payees. Enforced in the ledger *before* money moves — so even a compromised
  agent cannot exceed its wallet's hard limits. The spending policy is a
  protocol-level primitive, not application code.
- **x402 interceptor** — the killer feature. A `PayAwareSession` wraps any
  request: a `402 Payment Required` is auto-paid from the agent's wallet (within
  budget) and the call is transparently retried. Make an agent "pay-aware" with no
  per-integration code. Crucially it pays *through* the ledger, so the budget
  ceiling holds even if the SDK is tampered with.

**Phase 2 — the network effect (agents discover and trust each other)**
- **Agent registry** — discover providers by *capability* ("research",
  "translate", …), ranked cheapest-and-most-trusted first. Agent A hires Agent B
  without knowing it exists ahead of time.
- **Escrowed, outcome-based payment** — funds are held in a platform Vault and
  released to the provider only when the outcome is accepted, or refunded on
  failure. Solves the "who goes first" trust problem for agent-to-agent commerce.

**Phase 3 — the enterprise upsell (compliance)**
- **KYB/AML status** per agent and a **tamper-evident, hash-chained audit trail**
  of every settlement — the SOC 2 / audit surface enterprises need.

**Revenue model** — a **0.5% take rate** on settlement volume is skimmed into a
platform Treasury on every settled payment, surfaced live on the dashboard.

**Live ledger dashboard** — balances, budget burn-down, capability discovery,
escrow flows, platform revenue, and a real-time feed of every payment (including
ones **blocked by an agent's budget**).

## Architecture

```
frontend/  React + Vite dashboard  ──proxy──►  backend/  FastAPI
                                                 ├─ models.py      micro-USDC types + 0.5% take rate
                                                 ├─ store.py       in-memory datastore  ← Lemma datastore seam
                                                 ├─ ledger.py      transfers + budget enforcement + take rate
                                                 ├─ x402.py        402 challenge / pay / verify
                                                 ├─ interceptor.py PayAwareSession — transparent auto-pay (Phase 1)
                                                 ├─ registry.py    discover agents by capability       (Phase 2)
                                                 ├─ escrow.py      hold / release / refund             (Phase 2)
                                                 ├─ compliance.py  KYB/AML + hash-chained audit trail   (Phase 3)
                                                 ├─ agents.py      worker execution        ← Lemma agent seam
                                                 └─ lemma_adapter.py  hire/autopay/escrow  ← Lemma workflow seam
```

### The Lemma seam
Everything "infrastructure" is funnelled through one isolated seam. By default the
app runs on an in-memory store + mock agents so the payment rails are the star and
setup is zero. The real Lemma SDK is wired through a single module, `lemma_sdk.py`,
selected at runtime by environment variable:

```
AGENTPAY_BACKEND   memory | lemma         # default: memory
LEMMA_API_KEY      <your Lemma credential>   # required when backend=lemma
LEMMA_API_URL      <endpoint>                # optional
LEMMA_NETWORK      <settlement network>      # default: lemma-sim
```

- With `AGENTPAY_BACKEND=memory` (default) everything is simulated and offline.
- With `AGENTPAY_BACKEND=lemma` the app routes **agent execution** (`run_agent`)
  and **settlement mirroring** (every settled ledger event → a Lemma settlement,
  at the protocol seam) through `lemma_sdk.LemmaClient`. If the SDK isn't installed
  or a call isn't wired yet, the client reports `lemma_available: false` and the app
  **falls back to the simulated path** — it never crashes a demo. Check the active
  backend at `GET /v1/health` (also shown as a badge in the dashboard header).

**To go live:** `pip install` the hackathon Lemma package, set the env vars, and
fill in the three `TODO(lemma)` integration points in `lemma_sdk.py` —
`_connect` (client constructor), `invoke_agent` (`agents.invoke`), and
`mirror_settlement` (`settlements.create`) — from the SDK quickstart. No other file
changes. The datastore (`store.py`) is likewise swappable behind the same seam.

---

## Run it

**Prereqs:** Python 3.11+, Node 18+.

### 1. Backend (terminal 1) — uses a Python virtual environment
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python run.py                         # serves http://127.0.0.1:8000  (API docs at /docs)
```

### 2. Frontend (terminal 2)
```bash
cd frontend
npm install
npm run dev             # opens http://127.0.0.1:5173
```

Open the dashboard and click **▶ Run agent economy demo**, or use **Hire an
agent** to drive a single payment and watch the `402 → pay → 200` trace.

### Smoke test (no server needed)
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
$env:PYTHONPATH="."; python smoke_test.py
```

---

## API quick reference

| Method | Path | Purpose |
|---|---|---|
| GET  | `/v1/agents` | agents + wallets + budgets + KYB status |
| GET  | `/v1/transactions` | ledger feed (newest first) |
| GET  | `/v1/stats` | dashboard totals incl. platform revenue |
| GET  | `/v1/services/{agent_id}/invoke` | raw x402: `402` or, with `X-PAYMENT` header, the result |
| POST | `/v1/pay` | pay an x402 challenge → receipt |
| POST | `/v1/autopay` | **x402 interceptor**: transparent auto-pay + retry trace |
| POST | `/v1/hire` | one-click: client agent hires provider (full handshake + trace) |
| GET  | `/v1/registry` | **discover** providers by `capability` (ranked) |
| POST | `/v1/hire/escrow` | **outcome-based** hire via escrow (`simulate_outcome`) |
| GET  | `/v1/escrow` | list escrows |
| POST | `/v1/escrow/{id}/release` · `/refund` | settle a held escrow |
| GET  | `/v1/compliance/agents` | KYB/AML posture across the fleet |
| POST | `/v1/agents/{id}/kyb` | set an agent's KYB status |
| GET  | `/v1/compliance/audit` | hash-chained, tamper-evident audit trail |
| PUT  | `/v1/wallets/{id}/policy` | update programmable budget |
| POST | `/v1/wallets/{id}/topup` | faucet a wallet |
| POST | `/v1/demo/scenario` | scripted multi-agent demo (touches every rail) |
| POST | `/v1/demo/reset` | reseed |

## Roadmap (post-hackathon)
- Wire the Lemma SDK seam (datastores + agents + workflows) — reimplement
  `store.py` + `lemma_adapter.py`; everything else (registry, escrow, compliance,
  interceptor) rides on top unchanged.
- Swap the simulated ledger for a real testnet (Base + USDC) behind the same `x402.py`.
- Back the audit trail with a signed append-only store; real KYB/AML providers and
  fiat off-ramps for the Phase 3 enterprise tier.
- Streaming payments, agent reputation scoring, spend analytics.
