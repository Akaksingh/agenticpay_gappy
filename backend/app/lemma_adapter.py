"""Lemma SDK seam.

Everything the app needs from "infrastructure" is funnelled through this one
adapter: persistence (datastore), agent execution, and the end-to-end
hire-an-agent workflow. Today it's backed by the in-memory `Store` and the mock
worker agents. To go live on the hackathon Lemma SDK, reimplement these methods
with Lemma datastores / agents / workflows — no other file needs to change.

    TODO(lemma): replace the bodies below with Lemma SDK calls once the
    hackathon docs are available (paste them into the chat and I'll wire it in).
"""
from __future__ import annotations

import logging

from . import agents, escrow
from .interceptor import PayAwareSession
from .ledger import PaymentError
from .lemma_sdk import LemmaNotWired
from .lemma_sdk import client as lemma_client
from .models import Agent, fmt_usdc
from .store import Store
from .x402 import make_challenge, pay_challenge, verify_receipt

log = logging.getLogger("agentpay.adapter")


class LemmaAdapter:
    def __init__(self, store: Store) -> None:
        self.store = store

    # --- agent execution (Lemma agents) ----------------------------------
    def run_agent(self, agent: Agent, task_input: str) -> dict:
        """Execute the priced unit of work — on Lemma if wired, else the mock.

        When the Lemma backend is active this is a real `agents.invoke`; otherwise
        (or if that call isn't wired yet) it transparently falls back to the
        deterministic mock so the demo always produces a result.
        """
        if lemma_client.available:
            try:
                return lemma_client.invoke_agent(agent, task_input)
            except LemmaNotWired as e:
                log.warning("Lemma agent invoke not wired (%s) — using mock for %s.", e, agent.name)
            except Exception as e:  # noqa: BLE001 — degrade, don't crash a demo
                log.warning("Lemma agent invoke failed (%s) — using mock for %s.", e, agent.name)
        return agents.run_agent(agent, task_input)

    # --- a priced resource as an x402 endpoint (used by the interceptor) --
    def _resource_fetch(self, provider: Agent, task_input: str):
        """Return a `fetch(headers) -> (status, body)` for the provider's service.

        This is exactly what `GET /v1/services/{id}/invoke` does, expressed as a
        plain callable so the interceptor can drive it the way an SDK would drive
        any 402-speaking HTTP endpoint.
        """
        store = self.store
        resource = f"agent://{provider.id}/invoke"

        def fetch(headers: dict):
            receipt = headers.get("X-PAYMENT")
            if receipt is None:
                challenge = make_challenge(
                    store, resource, provider.wallet_id, provider.price_per_call,
                    description=f"{provider.name} · {', '.join(provider.skills) or 'work'}",
                )
                return 402, challenge
            if verify_receipt(store, receipt, resource) is None:
                return 402, {"error": "invalid_or_missing_payment"}
            return 200, {"ok": True, "result": self.run_agent(provider, task_input)}

        return fetch

    # --- the x402 interceptor in action ----------------------------------
    def autopay(self, client_id: str, provider_id: str, task_input: str) -> dict:
        """Drive a priced resource through the PayAwareSession (transparent auto-pay)."""
        client = self.store.agent(client_id)
        provider = self.store.agent(provider_id)
        if client is None or provider is None:
            raise PaymentError("unknown_agent")
        session = PayAwareSession(self.store, client.wallet_id)
        outcome = session.get(self._resource_fetch(provider, task_input))
        return {
            "client": client.name,
            "provider": provider.name,
            "ok": outcome["ok"],
            "reason": outcome.get("reason"),
            "result": (outcome.get("result") or {}).get("result"),
            "steps": [{**s, "who": f"{client.name} → {provider.name}"} for s in outcome["trace"]],
        }

    # --- outcome-based hire via escrow -----------------------------------
    def hire_with_escrow(self, client_id: str, provider_id: str, task_input: str,
                         simulate_outcome: str = "success") -> dict:
        """Hold payment in escrow, run the work, then release on success / refund on failure."""
        store = self.store
        client = store.agent(client_id)
        provider = store.agent(provider_id)
        if client is None or provider is None:
            raise PaymentError("unknown_agent")
        amount_fmt = fmt_usdc(provider.price_per_call)
        steps: list[dict] = []
        who = f"{client.name} → {provider.name}"

        # 1. Open escrow — funds leave the client (budget enforced) into the Vault.
        try:
            esc = escrow.open_escrow(store, client_id, provider_id, provider.price_per_call)
        except PaymentError as e:
            steps.append({"step": "payment_blocked", "who": who,
                          "detail": f"Escrow blocked by {client.name}'s budget: {e.reason}", "reason": e.reason})
            return {"ok": False, "reason": e.reason, "client": client.name,
                    "provider": provider.name, "steps": steps}
        steps.append({"step": "escrow_held", "who": who,
                      "detail": f"{amount_fmt} held in Escrow Vault pending outcome", "escrow": esc.id})

        # 2. Provider does the work.
        result = self.run_agent(provider, task_input)
        steps.append({"step": "work_delivered", "who": who, "detail": f"{provider.name} produced a result"})

        # 3. Settle the outcome: release to provider, or refund the client.
        if simulate_outcome == "failure":
            escrow.refund(store, esc.id, outcome="outcome_rejected")
            steps.append({"step": "payment_blocked", "who": who,
                          "detail": f"Outcome rejected — {amount_fmt} refunded to {client.name}", "escrow": esc.id})
            ok = False
        else:
            escrow.release(store, esc.id, outcome="outcome_accepted")
            steps.append({"step": "payment_settled", "who": who,
                          "detail": f"Outcome accepted — {amount_fmt} released to {provider.name}", "escrow": esc.id})
            ok = True

        return {"ok": ok, "client": client.name, "provider": provider.name,
                "amount": provider.price_per_call, "escrow": esc.to_public(),
                "result": result if ok else None, "steps": steps}

    # --- the headline workflow: one agent hires another ------------------
    def hire(self, client_id: str, provider_id: str, task_input: str) -> dict:
        """Run the full x402 handshake server-side and return a step-by-step trace.

        This is the "agent hires agent, settles instantly" story, with the real
        402 -> pay -> 200 sequence captured as `steps` so the UI can narrate it.
        """
        store = self.store
        client = store.agent(client_id)
        provider = store.agent(provider_id)
        if client is None or provider is None:
            raise PaymentError("unknown_agent")

        client_wallet = store.wallet(client.wallet_id)
        provider_wallet = store.wallet(provider.wallet_id)
        resource = f"agent://{provider.id}/invoke"
        steps: list[dict] = []

        # 1. Client calls the provider with no payment -> 402.
        challenge = make_challenge(
            store,
            resource=resource,
            pay_to_wallet=provider_wallet.id,
            amount=provider.price_per_call,
            description=f"{provider.name} · {', '.join(provider.skills) or 'work'}",
        )
        nonce = challenge["accepts"][0]["nonce"]
        steps.append({
            "step": "payment_required",
            "label": "402 payment_required",
            "detail": f"{provider.name} requires {challenge['accepts'][0]['amountFormatted']} to run",
            "amount": provider.price_per_call,
        })

        # 2. Client wallet pays the challenge (budget enforced inside settle()).
        try:
            receipt_id, pay_tx = pay_challenge(store, nonce, client_wallet.id)
        except PaymentError as e:
            steps.append({
                "step": "payment_blocked",
                "detail": f"Blocked by {client.name}'s budget: {e.reason}",
                "reason": e.reason,
            })
            return {
                "ok": False,
                "reason": e.reason,
                "client": client.name,
                "provider": provider.name,
                "steps": steps,
            }
        steps.append({
            "step": "payment_settled",
            "detail": f"{client.name} paid {provider.name} {challenge['accepts'][0]['amountFormatted']}",
            "tx": pay_tx.id,
        })

        # 3. Client retries with the receipt -> verified -> provider runs.
        if verify_receipt(store, receipt_id, resource) is None:
            raise PaymentError("invalid_receipt")
        result = self.run_agent(provider, task_input)
        steps.append({
            "step": "work_delivered",
            "detail": f"{provider.name} returned a result",
        })

        return {
            "ok": True,
            "client": client.name,
            "provider": provider.name,
            "amount": provider.price_per_call,
            "receipt": receipt_id,
            "tx": pay_tx.id,
            "result": result,
            "steps": steps,
        }
