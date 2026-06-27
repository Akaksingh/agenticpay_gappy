import { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";

const stripUsdc = (s) => (s || "").replace(" USDC", "");

export default function App() {
  const [agents, setAgents] = useState([]);
  const [txns, setTxns] = useState([]);
  const [stats, setStats] = useState({});
  const [trace, setTrace] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showCompliance, setShowCompliance] = useState(false);
  const [health, setHealth] = useState(null);

  const refresh = useCallback(async () => {
    const [a, t, s] = await Promise.all([api.agents(), api.transactions(), api.stats()]);
    setAgents(a.agents || []);
    setTxns(t.transactions || []);
    setStats(s || {});
  }, []);

  useEffect(() => {
    refresh();
    api.health().then(setHealth).catch(() => {});
    const id = setInterval(() => api.transactions().then((t) => setTxns(t.transactions || [])), 1500);
    return () => clearInterval(id);
  }, [refresh]);

  const orchestrators = agents.filter((a) => a.kind === "orchestrator");
  const providers = agents.filter((a) => a.kind === "worker" || a.kind === "service");

  function tracesFromResults(results, title) {
    const steps = [];
    for (const r of results) {
      for (const s of r.steps || []) steps.push({ ...s, who: s.who || `${r.client} → ${r.provider}` });
    }
    return { title, steps, results };
  }

  async function runScenario() {
    setBusy(true);
    setTrace({ title: "Atlas is orchestrating a multi-agent job…", steps: [] });
    const { results } = await api.scenario();
    setTrace(tracesFromResults(results, "Multi-agent job complete"));
    await refresh();
    setBusy(false);
  }

  async function reset() {
    setBusy(true);
    await api.reset();
    setTrace(null);
    setShowCompliance(false);
    await refresh();
    setBusy(false);
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo">◆</span>
          <div>
            <h1>AgentPay</h1>
            <p>Payment rails for AI agents · <span className="muted">powered by Lemma SDK</span></p>
          </div>
          {health && <BackendBadge health={health} />}
        </div>
        <div className="actions">
          <button className="btn ghost" disabled={busy} onClick={() => setShowCompliance((v) => !v)}>
            🛡 Compliance
          </button>
          <button className="btn primary" disabled={busy} onClick={runScenario}>▶ Run agent economy demo</button>
          <button className="btn ghost" disabled={busy} onClick={reset}>↻ Reset</button>
        </div>
      </header>

      <section className="stats">
        <Stat label="Payments settled" value={stats.total_payments ?? 0} />
        <Stat label="Settlement volume" value={stats.total_volume_fmt ?? "—"} accent />
        <Stat
          label={`Platform revenue · ${(stats.take_rate_bps ?? 0) / 100}%`}
          value={stats.platform_revenue_fmt ?? "—"}
          revenue
        />
        <Stat label="Budget blocks" value={stats.rejected ?? 0} danger={stats.rejected > 0} />
        <Stat label="Active agents" value={stats.agents ?? 0} />
      </section>

      {showCompliance && <CompliancePanel />}

      <main className="grid">
        <div className="col">
          <DiscoveryPanel orchestrators={orchestrators} setTrace={setTrace} onDone={refresh} />
          <h2 className="section">Agent wallets &amp; budgets</h2>
          {orchestrators.map((a) => <AgentCard key={a.id} a={a} hero />)}
          <div className="providers">
            {providers.map((a) => <AgentCard key={a.id} a={a} />)}
          </div>
        </div>

        <div className="col">
          <HirePanel agents={agents} onDone={refresh} setTrace={setTrace} />
          {trace && <TracePanel trace={trace} />}
          <h2 className="section">Live ledger</h2>
          <Ledger txns={txns} agents={agents} />
        </div>
      </main>
    </div>
  );
}

function BackendBadge({ health }) {
  const live = health.backend === "lemma" && health.lemma_available;
  const cls = live ? "live" : health.backend === "lemma" ? "pending" : "sim";
  const text = live ? "Lemma · live" : health.backend === "lemma" ? "Lemma · fallback" : "Simulated ledger";
  return <span className={`backend-badge ${cls}`} title={health.detail}>{text}</span>;
}

function Stat({ label, value, accent, danger, revenue }) {
  return (
    <div className={`stat ${accent ? "accent" : ""} ${danger ? "danger" : ""} ${revenue ? "revenue" : ""}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function KybBadge({ status }) {
  const map = { verified: "✓ KYB", pending: "◷ KYB", unverified: "✕ KYB" };
  return <span className={`kyb ${status}`}>{map[status] || status}</span>;
}

function AgentCard({ a, hero }) {
  const p = a.wallet.policy;
  const pct = Math.min(100, (p.spent_today / Math.max(1, p.daily_limit)) * 100);
  return (
    <div className={`card agent ${hero ? "hero" : ""}`}>
      <div className="agent-head">
        <span className="avatar">{a.avatar}</span>
        <div className="agent-id">
          <strong>{a.name}</strong>
          <div className="tag-row">
            <span className={`tag ${a.kind}`}>{a.kind}</span>
            <KybBadge status={a.kyb_status} />
          </div>
        </div>
        <div className="balance">{stripUsdc(a.wallet.balance_fmt)}<small>USDC</small></div>
      </div>
      {a.skills.length > 0 && (
        <div className="skills">{a.skills.map((s) => <span key={s} className="skill">{s}</span>)}
          {a.price_per_call > 0 && <span className="price">{stripUsdc(a.price_per_call_fmt)}/call</span>}
        </div>
      )}
      <div className="budget">
        <div className="budget-row">
          <span>Per-call cap</span><span>{p.per_call_limit_fmt}</span>
        </div>
        <div className="budget-row">
          <span>Daily spent</span><span>{p.spent_today_fmt} / {p.daily_limit_fmt}</span>
        </div>
        <div className="bar"><div className="bar-fill" style={{ width: `${pct}%` }} /></div>
      </div>
    </div>
  );
}

function DiscoveryPanel({ orchestrators, setTrace, onDone }) {
  const [caps, setCaps] = useState([]);
  const [cap, setCap] = useState("research");
  const [providers, setProviders] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (capability) => {
    const r = await api.registry(capability);
    setCaps(r.capabilities || []);
    setProviders(r.providers || []);
  }, []);

  useEffect(() => { load(cap); }, [cap, load]);

  async function hire(provider) {
    const client = orchestrators[0];
    if (!client) return;
    setBusy(true);
    const r = await api.autopay(client.id, provider.id, `capability: ${cap}`);
    setTrace({
      title: r.ok ? `${r.client} discovered & hired ${r.provider}` : `Auto-pay blocked`,
      steps: (r.steps || []).map((s) => ({ ...s, who: s.who || `${r.client} → ${r.provider}` })),
      results: [r],
    });
    await onDone();
    setBusy(false);
  }

  return (
    <div className="card discovery">
      <div className="disc-head">
        <h2 className="section nomargin">🛰 Discover agents by capability</h2>
        <select value={cap} onChange={(e) => setCap(e.target.value)}>
          {caps.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </div>
      <div className="disc-list">
        {providers.length === 0 && <p className="muted center">No providers for “{cap}”.</p>}
        {providers.map((p, i) => (
          <div key={p.id} className="disc-row">
            <span className="rank">#{i + 1}</span>
            <span className="disc-name">{p.avatar} {p.name}</span>
            <KybBadge status={p.kyb_status} />
            <span className="disc-price">{stripUsdc(p.price_per_call_fmt)}/call</span>
            <button className="btn tiny" disabled={busy} onClick={() => hire(p)}>⚡ Hire</button>
          </div>
        ))}
      </div>
    </div>
  );
}

function HirePanel({ agents, onDone, setTrace }) {
  const orchestrators = agents.filter((a) => a.kind === "orchestrator");
  const providers = agents.filter((a) => a.kind === "worker" || a.kind === "service");
  const [client, setClient] = useState("");
  const [provider, setProvider] = useState("");
  const [input, setInput] = useState("AI agent payments");
  const [mode, setMode] = useState("autopay"); // autopay | escrow_ok | escrow_fail
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!client && orchestrators[0]) setClient(orchestrators[0].id);
    if (!provider && providers[0]) setProvider(providers[0].id);
  }, [agents]);

  async function run() {
    setBusy(true);
    let r;
    if (mode === "autopay") r = await api.autopay(client, provider, input);
    else r = await api.hireEscrow(client, provider, input, mode === "escrow_fail" ? "failure" : "success");
    setTrace({
      title: r.ok ? `${r.client} → ${r.provider} settled` : `Payment not completed`,
      steps: (r.steps || []).map((s) => ({ ...s, who: s.who || `${r.client} → ${r.provider}` })),
      results: [r],
    });
    await onDone();
    setBusy(false);
  }

  const label = {
    autopay: "💸 Auto-pay & invoke (x402)",
    escrow_ok: "🔒 Escrow → accept outcome",
    escrow_fail: "🔒 Escrow → reject (refund)",
  }[mode];

  return (
    <div className="card hire">
      <h2 className="section nomargin">Hire an agent</h2>
      <div className="hire-form">
        <label>Client
          <select value={client} onChange={(e) => setClient(e.target.value)}>
            {orchestrators.concat(providers).map((a) => <option key={a.id} value={a.id}>{a.avatar} {a.name}</option>)}
          </select>
        </label>
        <label>Provider
          <select value={provider} onChange={(e) => setProvider(e.target.value)}>
            {providers.map((a) => <option key={a.id} value={a.id}>{a.avatar} {a.name} · {stripUsdc(a.price_per_call_fmt)}</option>)}
          </select>
        </label>
      </div>
      <label className="full">Task input
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="what should the agent do?" />
      </label>
      <div className="modes">
        <ModeChip id="autopay" mode={mode} setMode={setMode}>x402 interceptor</ModeChip>
        <ModeChip id="escrow_ok" mode={mode} setMode={setMode}>Escrow · accept</ModeChip>
        <ModeChip id="escrow_fail" mode={mode} setMode={setMode}>Escrow · refund</ModeChip>
      </div>
      <button className="btn primary full" disabled={busy} onClick={run}>
        {busy ? "Settling…" : label}
      </button>
    </div>
  );
}

function ModeChip({ id, mode, setMode, children }) {
  return (
    <button className={`mode-chip ${mode === id ? "on" : ""}`} onClick={() => setMode(id)}>
      {children}
    </button>
  );
}

function TracePanel({ trace }) {
  return (
    <div className="card trace">
      <h2 className="section nomargin">{trace.title}</h2>
      <ol className="steps">
        {trace.steps.map((s, i) => (
          <li key={i} className={`step ${s.step}`}>
            <span className="dot" />
            <div>
              <code>{s.label || s.step}</code>
              <span className="who">{s.who}</span>
              <p>{s.detail}</p>
            </div>
          </li>
        ))}
      </ol>
      {trace.results?.map((r, i) => r.ok && r.result && (
        <pre key={i} className="result">{JSON.stringify(r.result, null, 2)}</pre>
      ))}
    </div>
  );
}

function CompliancePanel() {
  const [kyb, setKyb] = useState(null);
  const [audit, setAudit] = useState(null);

  useEffect(() => {
    api.compliance().then(setKyb);
    api.audit().then(setAudit);
  }, []);

  return (
    <div className="card compliance">
      <h2 className="section nomargin">🛡 Enterprise compliance &amp; audit</h2>
      <p className="muted small">KYB/AML posture and a tamper-evident, hash-chained settlement log — the Phase 3 enterprise surface.</p>
      {kyb && (
        <div className="kyb-counts">
          <span className="kyb verified">✓ {kyb.counts.verified} verified</span>
          <span className="kyb pending">◷ {kyb.counts.pending} pending</span>
          <span className="kyb unverified">✕ {kyb.counts.unverified} unverified</span>
        </div>
      )}
      {audit && (
        <div className="audit">
          <div className="audit-head">
            <span>{audit.count} audit entries</span>
            <code className="hash">head {audit.head_hash}</code>
          </div>
          <div className="audit-list">
            {audit.entries.slice(-8).reverse().map((e) => (
              <div key={e.tx_id} className="audit-row">
                <span className={`kind ${e.kind}`}>{e.kind}</span>
                <span className={`audit-status ${e.status}`}>{e.status}</span>
                <span className="audit-amt">{e.amount_fmt}</span>
                <code className="hash">{e.hash}</code>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Ledger({ txns, agents }) {
  const name = (wid) => {
    const a = agents.find((x) => x.wallet.id === wid);
    return a ? `${a.avatar} ${a.name}` : wid ? "wallet" : "faucet";
  };
  return (
    <div className="card ledger">
      {txns.length === 0 && <p className="muted center">No transactions yet — run the demo.</p>}
      {txns.map((t) => (
        <div key={t.id} className={`txn ${t.status}`}>
          <span className={`kind ${t.kind}`}>{t.kind}</span>
          <span className="flow">{name(t.from_wallet)} <em>→</em> {name(t.to_wallet)}</span>
          <span className="memo">{t.status === "rejected" ? `blocked · ${t.reason}` : t.memo}</span>
          <span className={`amt ${t.status}`}>{t.status === "rejected" ? "✕" : ""}{stripUsdc(t.amount_fmt)}</span>
        </div>
      ))}
    </div>
  );
}
