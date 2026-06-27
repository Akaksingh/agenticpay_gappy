"""Quick end-to-end smoke test of the AgentPay API (no server needed)."""
from fastapi.testclient import TestClient

from app.main import app, store

c = TestClient(app)


def usdc(m):
    return f"{m/1_000_000:.4f}"


def main():
    agents = c.get("/v1/agents").json()["agents"]
    by_name = {a["name"]: a for a in agents}
    atlas, sage, ticker = by_name["Atlas"], by_name["Sage"], by_name["Ticker"]
    print("Seeded agents:", ", ".join(f"{a['name']}({usdc(a['wallet']['balance'])})" for a in agents))

    # 1. Raw x402: invoke without payment -> 402 challenge
    r = c.get(f"/v1/services/{ticker['id']}/invoke", params={"input": "ETH"})
    assert r.status_code == 402, r.status_code
    ch = r.json()["accepts"][0]
    print("\n[x402] 402 challenge:", ch["amountFormatted"], "->", ch["payTo"])

    # 2. Pay the challenge from Atlas's wallet
    r = c.post("/v1/pay", json={"nonce": ch["nonce"], "from_wallet": atlas["wallet"]["id"]})
    assert r.status_code == 200, r.text
    receipt = r.json()["receipt"]
    print("[x402] paid, receipt:", receipt, "tx:", r.json()["transaction"]["id"])

    # 3. Retry with receipt -> result
    r = c.get(f"/v1/services/{ticker['id']}/invoke",
              params={"input": "ETH"}, headers={"X-PAYMENT": receipt})
    assert r.status_code == 200, r.text
    print("[x402] result:", r.json()["result"])

    # 4. One-click hire (full handshake + trace)
    r = c.post("/v1/hire", json={"client_id": atlas["id"], "provider_id": sage["id"],
                                 "input": "AI agent payments"}).json()
    print("\n[hire] ok =", r["ok"], "| steps:")
    for s in r["steps"]:
        print("   -", s["step"], ":", s["detail"])

    # 5. Budget enforcement: tighten Atlas per-call cap below price, expect block
    c.put(f"/v1/wallets/{atlas['wallet']['id']}/policy", json={"per_call_usdc": 0.05})
    r = c.post("/v1/hire", json={"client_id": atlas["id"], "provider_id": sage["id"],
                                 "input": "blocked?"}).json()
    print("\n[budget] hire after lowering per-call cap to 0.05 -> ok =", r["ok"],
          "| reason =", r.get("reason"))
    assert r["ok"] is False and r["reason"] == "exceeds_per_call_limit"

    # 5b. The interceptor must respect the same protocol-level cap (the moat).
    r = c.post("/v1/autopay", json={"client_id": atlas["id"], "provider_id": sage["id"],
                                    "input": "x"}).json()
    print("[interceptor] auto-pay under tightened cap -> ok =", r["ok"], "| reason =", r.get("reason"))
    assert r["ok"] is False and r["reason"] == "exceeds_per_call_limit"
    c.put(f"/v1/wallets/{atlas['wallet']['id']}/policy", json={"per_call_usdc": 2.0})  # restore

    # 6. Registry discovery (Phase 2): find research providers, cheapest first.
    reg = c.get("/v1/registry", params={"capability": "research"}).json()
    names = [p["name"] for p in reg["providers"]]
    print("\n[registry] research providers (ranked):", names)
    assert "Sage" in names and "Orion" in names

    # 7. Escrow outcome-based hire (Phase 2): release on success, refund on failure.
    r = c.post("/v1/hire/escrow", json={"client_id": atlas["id"], "provider_id": sage["id"],
                                        "input": "AI agents", "simulate_outcome": "success"}).json()
    print("[escrow] success -> status =", r["escrow"]["status"])
    assert r["ok"] and r["escrow"]["status"] == "released"
    r = c.post("/v1/hire/escrow", json={"client_id": atlas["id"], "provider_id": sage["id"],
                                        "input": "AI agents", "simulate_outcome": "failure"}).json()
    print("[escrow] failure -> status =", r["escrow"]["status"])
    assert r["ok"] is False and r["escrow"]["status"] == "refunded"

    # 8. Compliance (Phase 3): KYB overview + tamper-evident audit chain.
    comp = c.get("/v1/compliance/agents").json()
    print("[compliance] KYB counts:", comp["counts"])
    audit = c.get("/v1/compliance/audit").json()
    print("[compliance] audit entries:", audit["count"], "| head:", audit["head_hash"])
    assert audit["count"] > 0 and audit["head_hash"]

    stats = c.get("/v1/stats").json()
    print("\n[stats]", stats)
    assert stats["platform_revenue"] > 0, "take rate should have accrued revenue"
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
