"""Runtime configuration for the AgentPay backend.

The whole app runs on an in-memory backend by default so the demo is zero-setup
and stage-safe. Setting `AGENTPAY_BACKEND=lemma` (plus a `LEMMA_API_KEY`) flips
agent execution and settlement mirroring onto the real Lemma SDK — see
`lemma_sdk.py` for the isolated call sites.

All knobs are environment variables so nothing secret lands in the repo:

    AGENTPAY_BACKEND   memory | lemma        (default: memory)
    LEMMA_API_KEY      Lemma SDK credential  (required when backend=lemma)
    LEMMA_API_URL      Lemma endpoint        (optional; SDK default otherwise)
    LEMMA_NETWORK      settlement network    (default: lemma-sim)
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    backend: str
    lemma_api_key: str | None
    lemma_api_url: str | None
    lemma_network: str

    @property
    def lemma_selected(self) -> bool:
        """True when the operator asked for the Lemma backend (regardless of readiness)."""
        return self.backend == "lemma"


def load_settings() -> Settings:
    return Settings(
        backend=os.environ.get("AGENTPAY_BACKEND", "memory").strip().lower(),
        lemma_api_key=os.environ.get("LEMMA_API_KEY") or None,
        lemma_api_url=os.environ.get("LEMMA_API_URL") or None,
        lemma_network=os.environ.get("LEMMA_NETWORK", "lemma-sim"),
    )


settings = load_settings()
