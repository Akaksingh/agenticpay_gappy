// Thin API client for the AgentPay backend. Calls are proxied to :8000 in dev.
const base = "";

async function req(path, opts = {}) {
  const res = await fetch(base + path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  return res.json();
}

export const api = {
  agents: () => req("/v1/agents"),
  transactions: (limit = 60) => req(`/v1/transactions?limit=${limit}`),
  stats: () => req("/v1/stats"),
  hire: (client_id, provider_id, input) =>
    req("/v1/hire", { method: "POST", body: JSON.stringify({ client_id, provider_id, input }) }),
  autopay: (client_id, provider_id, input) =>
    req("/v1/autopay", { method: "POST", body: JSON.stringify({ client_id, provider_id, input }) }),
  hireEscrow: (client_id, provider_id, input, simulate_outcome) =>
    req("/v1/hire/escrow", {
      method: "POST",
      body: JSON.stringify({ client_id, provider_id, input, simulate_outcome }),
    }),
  registry: (capability = "", max_price_usdc) => {
    const q = new URLSearchParams({ capability });
    if (max_price_usdc != null) q.set("max_price_usdc", max_price_usdc);
    return req(`/v1/registry?${q}`);
  },
  compliance: () => req("/v1/compliance/agents"),
  audit: () => req("/v1/compliance/audit"),
  health: () => req("/v1/health"),
  scenario: () => req("/v1/demo/scenario", { method: "POST" }),
  reset: () => req("/v1/demo/reset", { method: "POST" }),
  topup: (walletId, amount_usdc) =>
    req(`/v1/wallets/${walletId}/topup`, { method: "POST", body: JSON.stringify({ amount_usdc }) }),
  setPolicy: (walletId, body) =>
    req(`/v1/wallets/${walletId}/policy`, { method: "PUT", body: JSON.stringify(body) }),
};
