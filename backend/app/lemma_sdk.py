"""Real Lemma SDK client wrapper — the single place that imports `lemma`.

Design contract: this is the only module that talks to the Lemma SDK. Everything
else (ledger, adapter, x402) is SDK-agnostic. When `AGENTPAY_BACKEND=lemma` and a
`LEMMA_API_KEY` is present, the app routes agent execution and settlement
mirroring through here; otherwise this client reports `available == False` and the
app stays on its in-memory backend.

Why the real calls are stubbed: the Lemma SDK ships behind the hackathon Discord,
not a public index, so its exact symbols (client constructor, agent-invoke and
settlement methods) aren't known here. Rather than invent method names that would
break at runtime, the three integration points below raise `LemmaNotWired` with a
clear message. Filling them in from the SDK quickstart is the entire "go-live"
task — no other file changes. Until then, callers catch `LemmaNotWired` and fall
back to the simulated path, so the demo never breaks.

    TODO(lemma): implement `_connect`, `invoke_agent`, and `mirror_settlement`
    against the SDK quickstart (install + client init + agent + settlement APIs).
"""
from __future__ import annotations

import importlib
import logging

from .config import settings

log = logging.getLogger("agentpay.lemma")

# Candidate import names for the SDK — the real one is confirmed at connect time.
_CANDIDATE_MODULES = ("lemma", "lemma_sdk", "lemmasdk")


class LemmaNotWired(RuntimeError):
    """Raised by an integration point that still needs SDK-specific code."""


class LemmaClient:
    def __init__(self) -> None:
        self._sdk = None       # the imported SDK module
        self._client = None    # the constructed SDK client
        self.available = False
        self.reason = "backend=memory"
        if settings.lemma_selected:
            self._init()

    # --- lifecycle --------------------------------------------------------
    def _init(self) -> None:
        if not settings.lemma_api_key:
            self.reason = "AGENTPAY_BACKEND=lemma but LEMMA_API_KEY is unset"
            log.warning("Lemma backend selected but no LEMMA_API_KEY — staying on in-memory backend.")
            return
        self._sdk = self._import_sdk()
        if self._sdk is None:
            self.reason = "Lemma SDK not installed (pip install the hackathon package)"
            log.warning("Lemma backend selected but SDK import failed — staying on in-memory backend.")
            return
        try:
            self._client = self._connect(self._sdk)
            self.available = True
            self.reason = "connected"
            log.info("Lemma backend active (network=%s).", settings.lemma_network)
        except LemmaNotWired as e:
            # Expected until the SDK call sites are filled in from the docs.
            self.reason = f"not wired: {e}"
            log.warning("Lemma SDK present but client not wired yet (%s) — falling back to in-memory.", e)
        except Exception as e:  # noqa: BLE001 — never let SDK init crash the app
            self.reason = f"connect_error: {e}"
            log.warning("Lemma client init failed (%s) — falling back to in-memory.", e)

    @staticmethod
    def _import_sdk():
        for name in _CANDIDATE_MODULES:
            try:
                return importlib.import_module(name)
            except ImportError:
                continue
        return None

    # --- integration points (fill these from the SDK quickstart) ----------
    def _connect(self, sdk):
        """Construct and return an authenticated Lemma client."""
        # TODO(lemma): e.g. `return sdk.Client(api_key=settings.lemma_api_key,
        #                                       base_url=settings.lemma_api_url)`
        raise LemmaNotWired("client constructor unknown — see SDK quickstart")

    def invoke_agent(self, agent, task_input: str) -> dict:
        """Run a priced unit of work on Lemma; return the agent's result payload."""
        if not self.available:
            raise LemmaNotWired(self.reason)
        # TODO(lemma): e.g. `return self._client.agents.invoke(agent.lemma_ref,
        #                                                       input=task_input)`
        raise LemmaNotWired("agents.invoke mapping unknown — see SDK quickstart")

    def mirror_settlement(self, *, tx_id: str, from_ref: str | None, to_ref: str | None,
                          amount: int, kind: str, memo: str) -> None:
        """Record an AgentPay settlement as a Lemma settlement event (cryptographic finality).

        Best-effort: callers invoke this fire-and-forget after a local settle, so a
        Lemma hiccup degrades to "local-only" rather than failing the payment.
        """
        if not self.available:
            raise LemmaNotWired(self.reason)
        # TODO(lemma): e.g. `self._client.settlements.create(idempotency_key=tx_id,
        #     payer=from_ref, payee=to_ref, amount=amount, asset="USDC",
        #     network=settings.lemma_network, memo=memo)`
        raise LemmaNotWired("settlements.create mapping unknown — see SDK quickstart")

    # --- status -----------------------------------------------------------
    def status(self) -> dict:
        return {
            "backend": settings.backend,
            "lemma_available": self.available,
            "network": settings.lemma_network,
            "detail": self.reason,
        }


# Process-wide singleton; cheap and inert unless the Lemma backend is selected.
client = LemmaClient()
