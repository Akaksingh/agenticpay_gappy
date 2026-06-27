"""Mock worker-agent execution.

This is the **Lemma agent seam**. Today each worker returns a deterministic,
stage-safe result so the payment flow is the star of the demo. When the Lemma
SDK is wired in, `run_agent` becomes a Lemma agent invocation (the priced unit
of work that the x402 micropayment pays for).
"""
from __future__ import annotations

from .models import Agent


def run_agent(agent: Agent, task_input: str) -> dict:
    text = (task_input or "").strip()
    skills = set(agent.skills)

    if "research" in skills:
        return {
            "type": "research_brief",
            "query": text or "the topic",
            "findings": [
                f"Market for '{text or 'the topic'}' is growing ~38% YoY.",
                "Three incumbents control ~60% share; long tail is fragmented.",
                "Regulatory clarity expected next quarter — key tailwind.",
            ],
        }
    if "translate" in skills:
        return {
            "type": "translation",
            "source": text,
            "target_lang": "es",
            "translation": f"[es] {text[::-1]}",  # placeholder transform
        }
    if "market-data" in skills:
        symbol = (text or "BTC").upper()
        # deterministic pseudo-price from the symbol so demos are reproducible
        base = sum(ord(c) for c in symbol) * 17.3
        return {"type": "quote", "symbol": symbol, "price_usd": round(1000 + base, 2)}
    if "summarize" in skills:
        return {
            "type": "summary",
            "summary": (text[:120] + "…") if len(text) > 120 else (text or "(nothing to summarize)"),
            "tokens": len(text.split()),
        }

    return {"type": "echo", "output": text or "(no input)"}
