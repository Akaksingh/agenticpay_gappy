import { useEffect, useState, useCallback } from "react";
import { api } from "./api.js";
import { Icon } from "./Icon.jsx";

const stripUsdc = (s) => (s || "").replace(" USDC", "");

// Plain-language labels so non-technical users understand what they see.
const KIND_LABEL = { orchestrator: "Manager AI", worker: "Specialist AI", service: "Service AI", platform: "Platform" };
const KIND_HELP = {
  orchestrator: "Hires other AIs and pays them for you",
  worker: "Does one job well, charges per task",
  service: "Offers a paid service to other AIs",
  platform: "AgentPay itself",
};

const initials = (name = "") =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "AI";

export default function App() {
  const [agents, setAgents] = useState([]);
  const [txns, setTxns] = useState([]);
  const [stats, setStats] = useState({});
  const [health, setHealth] = useState(null);
  const [view, setView] = useState("home");
  const [sheet, setSheet] = useState(null);
  const [trace, setTrace] = useState(null);
  const [busy, setBusy] = useState(false);

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
  const primary = orchestrators[0];

  function showTrace(t) { setTrace(t); setSheet("trace"); }

  async function runScenario() {
    setBusy(true);
    setTrace({ title: "Your Manager AI is working", subtitle: "Hiring specialists and paying them automatically", steps: [] });
    setSheet("trace");
    const { results } = await api.scenario();
    const steps = [];
    for (const r of results) for (const s of r.steps || []) steps.push({ ...s, who: s.who || `${r.client} - ${r.provider}` });
    setTrace({ title: "All done", subtitle: "Here is everything that happened", steps, results });
    await refresh();
    setBusy(false);
  }

  async function reset() {
    setBusy(true);
    await api.reset();
    setTrace(null); setSheet(null); setView("home");
    await refresh();
    setBusy(false);
  }

  return (
    <div className="app">
      <Navbar view={view} setView={setView} health={health} onAddMoney={() => setSheet("topup")} />

      <main className="container">
        {view === "home" && (
          <Home
            primary={primary} stats={stats} txns={txns} agents={agents} busy={busy}
            onOpen={setSheet} onRunDemo={runScenario} onReset={reset} onSeeAll={() => setView("activity")}
          />
        )}
        {view === "agents" && <AgentsView orchestrators={orchestrators} providers={providers} />}
        {view === "activity" && (
          <section className="block">
            <h2 className="block-title">Payment history</h2>
            <p className="block-sub">Every payment between your AIs, updated live.</p>
            <ActivityList txns={txns} agents={agents} />
          </section>
        )}
        {view === "help" && <HelpView />}
      </main>

      <SiteFooter setView={setView} setSheet={setSheet} />


      {sheet === "hire" && (
        <Modal title="Hire an AI" subtitle="Pay an AI to do a task for you" onClose={() => setSheet(null)}>
          <HireSheet agents={agents} busy={busy} setBusy={setBusy} onDone={refresh} onTrace={showTrace} />
        </Modal>
      )}
      {sheet === "discover" && (
        <Modal title="Find an AI by skill" subtitle="Compare AIs and hire the best fit" onClose={() => setSheet(null)}>
          <DiscoverSheet orchestrators={orchestrators} busy={busy} setBusy={setBusy} onDone={refresh} onTrace={showTrace} />
        </Modal>
      )}
      {sheet === "topup" && (
        <Modal title="Add money" subtitle="Top up a wallet so it can pay for jobs" onClose={() => setSheet(null)}>
          <TopUpSheet agents={agents} primary={primary} onDone={refresh} onClose={() => setSheet(null)} />
        </Modal>
      )}
      {sheet === "compliance" && (
        <Modal title="Safety and records" subtitle="Verification status and secure payment log" onClose={() => setSheet(null)}>
          <ComplianceSheet />
        </Modal>
      )}
      {sheet === "trace" && trace && (
        <Modal title={trace.title} subtitle={trace.subtitle} onClose={() => setSheet(null)}>
          <TraceSheet trace={trace} />
        </Modal>
      )}
    </div>
  );
}

/* ---------- Footer (contact & support) ---------- */
function SiteFooter({ setView, setSheet }) {
  return (
    <footer className="footer">
      <div className="footer-inner">
        <div className="footer-brand">
          <div className="footer-logo">
            <span className="nav-logo"><Icon name="logo" /></span>
            <strong>AgentPay</strong>
          </div>
          <p>Simple, safe payments for your AI helpers. Set the limits, let your AIs handle the rest.</p>
        </div>

        <div className="footer-col">
          <h4>Support</h4>
          <button className="foot-link" onClick={() => setView("help")}>How it works</button>
          <button className="foot-link" onClick={() => setSheet("compliance")}>Safety &amp; records</button>
          <button className="foot-link" onClick={() => setView("activity")}>Payment history</button>
          <button className="foot-link" onClick={() => setView("help")}>FAQs</button>
        </div>

        <div className="footer-col">
          <h4>Company</h4>
          <button className="foot-link" onClick={() => setView("home")}>About AgentPay</button>
          <button className="foot-link" onClick={() => setView("agents")}>Your AIs</button>
          <a className="foot-link" href="https://lemma.dev" target="_blank" rel="noreferrer">Lemma SDK</a>
          <span className="foot-link muted">Pricing - 0.5% per payment</span>
        </div>

        <div className="footer-col">
          <h4>Contact us</h4>
          <a className="foot-link" href="mailto:support@agentpay.io">support@agentpay.io</a>
          <a className="foot-link" href="tel:+18005550199">+1 (800) 555-0199</a>
          <span className="foot-link muted">Mon-Fri, 9am-6pm</span>
          <span className="foot-link muted">San Francisco, CA</span>
        </div>
      </div>

      <div className="footer-bottom">
        <span>© 2026 AgentPay. All rights reserved.</span>
        <span>Powered by the Lemma SDK · settled in USDC</span>
      </div>
    </footer>
  );
}

/* ---------- Navbar ---------- */
function Navbar({ view, setView, health, onAddMoney }) {
  const tabs = [
    { id: "home", label: "Home" },
    { id: "agents", label: "My AIs" },
    { id: "activity", label: "History" },
    { id: "help", label: "Help" },
  ];
  return (
    <header className="navbar">
      <div className="nav-inner">
        <div className="nav-brand" onClick={() => setView("home")}>
          <span className="nav-logo"><Icon name="logo" /></span>
          <strong>AgentPay</strong>
        </div>
        <nav className="nav-links">
          {tabs.map((t) => (
            <button key={t.id} className={`nav-link ${view === t.id ? "on" : ""}`} onClick={() => setView(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="nav-right">
          {health && <BackendBadge health={health} />}
          <button className="btn primary sm" onClick={onAddMoney}><Icon name="plus" /> Add money</button>
        </div>
      </div>
    </header>
  );
}

function BackendBadge({ health }) {
  const live = health.backend === "lemma" && health.lemma_available;
  const cls = live ? "live" : health.backend === "lemma" ? "pending" : "sim";
  const text = live ? "Live" : health.backend === "lemma" ? "Connecting" : "Demo mode";
  return <span className={`backend-badge ${cls}`} title={health.detail}><span className="bdot" />{text}</span>;
}

/* ---------- Home ---------- */
function Home({ primary, stats, txns, agents, busy, onOpen, onRunDemo, onReset, onSeeAll }) {
  const actions = [
    { id: "hire", icon: "hire", label: "Hire an AI", onClick: () => onOpen("hire") },
    { id: "discover", icon: "search", label: "Find by skill", onClick: () => onOpen("discover") },
    { id: "topup", icon: "wallet", label: "Add money", onClick: () => onOpen("topup") },
    { id: "demo", icon: "play", label: "Run demo", onClick: onRunDemo, disabled: busy },
    { id: "safety", icon: "shield", label: "Safety", onClick: () => onOpen("compliance") },
    { id: "reset", icon: "reset", label: "Reset", onClick: onReset, disabled: busy },
  ];
  return (
    <>
      <section className="hero">
        <div className="hero-wallet">
          <span className="hero-label">{primary ? `${primary.name}'s wallet` : "Your wallet"}</span>
          <div className="hero-amount">{primary ? stripUsdc(primary.wallet.balance_fmt) : "0.00"} <span>USDC</span></div>
          <button className="btn light" onClick={() => onOpen("topup")}><Icon name="plus" /> Add money</button>
          <p className="hero-hint">Spending always stays inside the limits you set.</p>
        </div>
        <div className="hero-actions">
          {actions.map((a) => (
            <button key={a.id} className="tile" onClick={a.onClick} disabled={a.disabled}>
              <span className="tile-icon"><Icon name={a.icon} /></span>
              <span className="tile-label">{a.label}</span>
            </button>
          ))}
        </div>
      </section>

      <StatRow stats={stats} />

      <section className="block">
        <div className="block-head">
          <h2 className="block-title">Recent activity</h2>
          <button className="link" onClick={onSeeAll}>See all</button>
        </div>
        <ActivityList txns={txns.slice(0, 6)} agents={agents} />
      </section>
    </>
  );
}

function StatRow({ stats }) {
  const items = [
    { label: "Payments made", value: stats.total_payments ?? 0 },
    { label: "Total paid", value: stats.total_volume_fmt ? stripUsdc(stats.total_volume_fmt) : "0.00" },
    { label: `Platform fee (${(stats.take_rate_bps ?? 0) / 100}%)`, value: stats.platform_revenue_fmt ? stripUsdc(stats.platform_revenue_fmt) : "0.00", good: true },
    { label: "Blocked (over limit)", value: stats.rejected ?? 0, warn: (stats.rejected ?? 0) > 0 },
  ];
  return (
    <section className="summary">
      {items.map((s) => (
        <div key={s.label} className={`summary-item ${s.good ? "good" : ""} ${s.warn ? "warn" : ""}`}>
          <span className="summary-value">{s.value}</span>
          <span className="summary-label">{s.label}</span>
        </div>
      ))}
    </section>
  );
}

/* ---------- Agents view ---------- */
function AgentsView({ orchestrators, providers }) {
  return (
    <>
      <section className="block">
        <h2 className="block-title">Your managers</h2>
        <p className="block-sub">These AIs hire others and pay on your behalf.</p>
        <div className="agent-grid">{orchestrators.map((a) => <AgentCard key={a.id} a={a} hero />)}</div>
      </section>
      <section className="block">
        <h2 className="block-title">Available specialists</h2>
        <p className="block-sub">Skilled AIs your managers can pay to do a job.</p>
        <div className="agent-grid">{providers.map((a) => <AgentCard key={a.id} a={a} />)}</div>
      </section>
    </>
  );
}

function AgentCard({ a, hero }) {
  const p = a.wallet.policy;
  const pct = Math.min(100, (p.spent_today / Math.max(1, p.daily_limit)) * 100);
  return (
    <div className={`card agent ${hero ? "hero" : ""}`}>
      <div className="agent-head">
        <span className="avatar">{initials(a.name)}</span>
        <div className="agent-id">
          <strong>{a.name}</strong>
          <span className="agent-kind">{KIND_LABEL[a.kind] || a.kind}</span>
        </div>
        <div className="balance">{stripUsdc(a.wallet.balance_fmt)}<small>USDC</small></div>
      </div>
      <p className="agent-help">{KIND_HELP[a.kind]}</p>

      <div className="agent-tags">
        <KybBadge status={a.kyb_status} />
        {a.skills.map((s) => <span key={s} className="skill">{s}</span>)}
        {a.price_per_call > 0 && <span className="price">{stripUsdc(a.price_per_call_fmt)}/job</span>}
      </div>

      <div className="budget">
        <div className="budget-row"><span>Spent today</span><span>{p.spent_today_fmt} of {p.daily_limit_fmt}</span></div>
        <div className="bar"><div className="bar-fill" style={{ width: `${pct}%` }} /></div>
        <div className="budget-row sub"><span>Max per job</span><span>{p.per_call_limit_fmt}</span></div>
      </div>
    </div>
  );
}

function KybBadge({ status }) {
  const map = { verified: "Verified business", pending: "Verifying", unverified: "Not verified" };
  return <span className={`kyb ${status}`}><span className="kdot" />{map[status] || status}</span>;
}

/* ---------- Activity list ---------- */
function ActivityList({ txns, agents }) {
  const name = (wid) => {
    const a = agents.find((x) => x.wallet.id === wid);
    return a ? a.name : wid ? "Wallet" : "Bank";
  };
  if (txns.length === 0) return <p className="empty">No payments yet. Use "Run demo" to see it in action.</p>;
  return (
    <div className="activity card">
      {txns.map((t) => {
        const blocked = t.status === "rejected";
        return (
          <div key={t.id} className={`row ${blocked ? "blocked" : ""}`}>
            <span className="row-icon"><Icon name={blocked ? "block" : "transfer"} /></span>
            <div className="row-main">
              <span className="row-title">{name(t.from_wallet)} <Icon name="arrow" /> {name(t.to_wallet)}</span>
              <span className="row-sub">{blocked ? `Blocked - ${t.reason}` : (t.memo || t.kind)}</span>
            </div>
            <span className={`row-amt ${blocked ? "neg" : ""}`}>{blocked ? "-" : ""}{stripUsdc(t.amount_fmt)}</span>
          </div>
        );
      })}
    </div>
  );
}

/* ---------- Modal ---------- */
function Modal({ title, subtitle, onClose, children }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <h3>{title}</h3>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="modal-close" onClick={onClose}><Icon name="close" /></button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

function Field({ label, children }) {
  return <label className="field"><span className="field-label">{label}</span>{children}</label>;
}

/* ---------- Hire ---------- */
function HireSheet({ agents, busy, setBusy, onDone, onTrace }) {
  const orchestrators = agents.filter((a) => a.kind === "orchestrator");
  const providers = agents.filter((a) => a.kind === "worker" || a.kind === "service");
  const [client, setClient] = useState(orchestrators[0]?.id || "");
  const [provider, setProvider] = useState(providers[0]?.id || "");
  const [input, setInput] = useState("Research AI agent payments");
  const [mode, setMode] = useState("autopay");

  async function run() {
    setBusy(true);
    let r;
    if (mode === "autopay") r = await api.autopay(client, provider, input);
    else r = await api.hireEscrow(client, provider, input, mode === "escrow_fail" ? "failure" : "success");
    onTrace({
      title: r.ok ? "Payment complete" : "Payment not completed",
      subtitle: `${r.client} - ${r.provider}`,
      steps: (r.steps || []).map((s) => ({ ...s, who: s.who || `${r.client} - ${r.provider}` })),
      results: [r],
    });
    await onDone();
    setBusy(false);
  }

  return (
    <div className="form">
      <Field label="Who is paying?">
        <select value={client} onChange={(e) => setClient(e.target.value)}>
          {orchestrators.concat(providers).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
        </select>
      </Field>
      <Field label="Who are you hiring?">
        <select value={provider} onChange={(e) => setProvider(e.target.value)}>
          {providers.map((a) => <option key={a.id} value={a.id}>{a.name} - {stripUsdc(a.price_per_call_fmt)}/job</option>)}
        </select>
      </Field>
      <Field label="What should they do?">
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Describe the task" />
      </Field>

      <span className="form-label">How should the money be handled?</span>
      <div className="choices">
        <Choice on={mode === "autopay"} onClick={() => setMode("autopay")} title="Pay and use now" sub="Instant payment, get the result right away" />
        <Choice on={mode === "escrow_ok"} onClick={() => setMode("escrow_ok")} title="Hold, release on success" sub="Money is held safely until the job is done" />
        <Choice on={mode === "escrow_fail"} onClick={() => setMode("escrow_fail")} title="Hold, refund if it fails" sub="Get your money back if the job does not work out" />
      </div>

      <button className="btn primary full" disabled={busy} onClick={run}>{busy ? "Processing" : "Confirm and pay"}</button>
    </div>
  );
}

function Choice({ on, onClick, title, sub }) {
  return (
    <button className={`choice ${on ? "on" : ""}`} onClick={onClick}>
      <span className="choice-radio">{on && <span className="choice-dot" />}</span>
      <span className="choice-text"><strong>{title}</strong><small>{sub}</small></span>
    </button>
  );
}

/* ---------- Discover ---------- */
function DiscoverSheet({ orchestrators, busy, setBusy, onDone, onTrace }) {
  const [caps, setCaps] = useState([]);
  const [cap, setCap] = useState("research");
  const [providers, setProviders] = useState([]);

  const load = useCallback(async (capability) => {
    const r = await api.registry(capability);
    setCaps(r.capabilities || []);
    setProviders(r.providers || []);
  }, []);
  useEffect(() => { load(cap); }, [cap, load]);

  async function hire(p) {
    const client = orchestrators[0];
    if (!client) return;
    setBusy(true);
    const r = await api.autopay(client.id, p.id, `capability: ${cap}`);
    onTrace({
      title: r.ok ? "Hired and paid" : "Could not complete",
      subtitle: `${r.client} - ${r.provider}`,
      steps: (r.steps || []).map((s) => ({ ...s, who: s.who || `${r.client} - ${r.provider}` })),
      results: [r],
    });
    await onDone();
    setBusy(false);
  }

  return (
    <div className="form">
      <Field label="What skill do you need?">
        <select value={cap} onChange={(e) => setCap(e.target.value)}>
          {caps.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </Field>
      <span className="form-label">Best matches (cheapest first)</span>
      <div className="disc-list">
        {providers.length === 0 && <p className="empty">No AIs offer "{cap}" yet.</p>}
        {providers.map((p, i) => (
          <div key={p.id} className="disc-row">
            <span className="avatar sm">{initials(p.name)}</span>
            <div className="disc-main">
              <span className="disc-name">{p.name}</span>
              <KybBadge status={p.kyb_status} />
            </div>
            <span className="disc-price">{stripUsdc(p.price_per_call_fmt)}/job</span>
            <button className="btn primary sm" disabled={busy} onClick={() => hire(p)}>Hire</button>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------- Top up ---------- */
function TopUpSheet({ agents, primary, onDone, onClose }) {
  const [walletId, setWalletId] = useState(primary?.wallet.id || agents[0]?.wallet.id || "");
  const [amount, setAmount] = useState(50);
  const [busy, setBusy] = useState(false);
  const chips = [10, 25, 50, 100, 250];

  async function add() {
    if (!walletId || !amount) return;
    setBusy(true);
    await api.topup(walletId, Number(amount));
    await onDone();
    setBusy(false);
    onClose();
  }

  return (
    <div className="form">
      <Field label="Add to which wallet?">
        <select value={walletId} onChange={(e) => setWalletId(e.target.value)}>
          {agents.map((a) => <option key={a.id} value={a.wallet.id}>{a.name} - {stripUsdc(a.wallet.balance_fmt)} USDC</option>)}
        </select>
      </Field>
      <Field label="Amount (USDC)">
        <input type="number" min="1" value={amount} onChange={(e) => setAmount(e.target.value)} />
      </Field>
      <div className="amount-chips">
        {chips.map((c) => (
          <button key={c} className={`amt-chip ${Number(amount) === c ? "on" : ""}`} onClick={() => setAmount(c)}>+{c}</button>
        ))}
      </div>
      <button className="btn primary full" disabled={busy} onClick={add}>{busy ? "Adding" : `Add ${amount} USDC`}</button>
    </div>
  );
}

/* ---------- Compliance ---------- */
function ComplianceSheet() {
  const [kyb, setKyb] = useState(null);
  const [audit, setAudit] = useState(null);
  useEffect(() => {
    api.compliance().then(setKyb);
    api.audit().then(setAudit);
  }, []);
  return (
    <div className="form">
      <p className="block-sub">We check that each AI belongs to a real, verified business, and we keep a tamper-proof record of every payment.</p>
      {kyb && (
        <div className="kyb-counts">
          <span className="kyb verified"><span className="kdot" />{kyb.counts.verified} verified</span>
          <span className="kyb pending"><span className="kdot" />{kyb.counts.pending} verifying</span>
          <span className="kyb unverified"><span className="kdot" />{kyb.counts.unverified} not verified</span>
        </div>
      )}
      {audit && (
        <>
          <span className="form-label">Secure payment log - {audit.count} records</span>
          <div className="audit-list">
            {audit.entries.slice(-8).reverse().map((e) => (
              <div key={e.tx_id} className="audit-row">
                <span className="audit-kind">{e.kind}</span>
                <span className={`audit-status ${e.status}`}>{e.status}</span>
                <span className="audit-amt">{e.amount_fmt}</span>
              </div>
            ))}
          </div>
          <p className="hash-note">Locked with secure code <code>{audit.head_hash}</code>. Records cannot be changed.</p>
        </>
      )}
    </div>
  );
}

/* ---------- Trace ---------- */
function TraceSheet({ trace }) {
  if (trace.steps.length === 0) return <p className="empty">Working...</p>;
  return (
    <div className="trace">
      <ol className="steps">
        {trace.steps.map((s, i) => (
          <li key={i} className={`step ${s.step}`}>
            <span className="dot" />
            <div className="step-body">
              <span className="step-label">{s.label || s.step}</span>
              <span className="step-who">{s.who}</span>
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

/* ---------- Help ---------- */
function HelpView() {
  const steps = [
    { icon: "wallet", title: "Add money to a wallet", text: "Each AI has its own wallet. Top it up so it can pay for jobs." },
    { icon: "shield", title: "Set safe spending limits", text: "Every AI has a daily limit and a max-per-job cap. Anything over is blocked automatically." },
    { icon: "hire", title: "Hire an AI to do a task", text: "Pick who pays and who works. Money moves only when the job is agreed." },
    { icon: "lock", title: "Use hold for safety", text: "Held payments are released only if the job succeeds, and refunded if it does not." },
    { icon: "receipt", title: "See every payment", text: "The History tab shows each payment as it happens, with plain descriptions." },
  ];
  return (
    <section className="block">
      <h2 className="block-title">How AgentPay works</h2>
      <p className="block-sub">AgentPay lets your AI helpers pay each other for work, safely, with limits you control.</p>
      <div className="help-list">
        {steps.map((s) => (
          <div key={s.title} className="help-item">
            <span className="help-icon"><Icon name={s.icon} /></span>
            <div><strong>{s.title}</strong><p>{s.text}</p></div>
          </div>
        ))}
      </div>
    </section>
  );
}
