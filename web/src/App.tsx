import { useEffect, useRef, useState } from 'react';
import {
  Activity, ArrowDown, ArrowDownToLine, ArrowRight, ArrowUpRight, Bot, Box,
  Check, CheckCircle2, ChevronDown, ChevronRight, CircleDot, Clock3, Code2,
  FileCode2, FlaskConical, GitBranch, GitCompareArrows, History, Info,
  LoaderCircle, Mail, MessageSquare, Play, Plus, RotateCcw,
  ShieldCheck, Sparkles, Terminal, Truck, Users, Wallet, Wrench, X,
} from 'lucide-react';
import { api } from './api';
import type { Agent, Run, RunEvent, Scenario, Suggestion } from './types';

type Page = 'workspace' | 'history' | 'configuration' | 'guide';
type TimelineTab = 'conversation' | 'checks';
const number = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 });
const date = (value: string) => new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';

function AgentIcon({ agent }: { agent: Agent }) {
  const role = `${agent.role} ${agent.name} ${agent.id}`.toLowerCase();
  if (/logistic|transport|carrier/.test(role)) return <Truck size={20} />;
  if (/supervis|policy|review/.test(role)) return <ShieldCheck size={20} />;
  if (/supplier|inventory/.test(role)) return <Box size={20} />;
  return <Users size={20} />;
}

function App() {
  const [page, setPage] = useState<Page>('workspace');
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState('');
  const [runs, setRuns] = useState<Run[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [parentCache, setParentCache] = useState<Record<string, Run>>({});
  const [loading, setLoading] = useState(true);
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [timelineTab, setTimelineTab] = useState<TimelineTab>('conversation');
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [editor, setEditor] = useState('');
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [editorError, setEditorError] = useState<string | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState('');
  const [importName, setImportName] = useState('');
  const [importError, setImportError] = useState<string | null>(null);
  const [importedIds, setImportedIds] = useState<string[]>([]);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const scenario = scenarios.find((item) => item.id === scenarioId);
  const selectedRun = runs.find((run) => run.id === selectedRunId);
  const parent = selectedRun?.parent_run_id ? runs.find((run) => run.id === selectedRun.parent_run_id) ?? parentCache[selectedRun.parent_run_id] : undefined;
  const scenarioRuns = runs.filter((run) => run.scenario_id === scenarioId);
  const savedJSON = scenario ? JSON.stringify(scenario, null, 2) : '';
  const dirty = editor !== savedJSON;
  const visibleRun = selectedRun?.scenario_id === scenarioId ? selectedRun : undefined;
  const displayedScenario = visibleRun?.configuration ?? scenario;

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [health, savedScenarios, savedRuns] = await Promise.all([
        api<{ status: string }>('/health'), api<Scenario[]>('/scenarios'), api<Run[]>('/runs'),
      ]);
      setConnected(health.status === 'ok');
      setScenarios(savedScenarios);
      setRuns(savedRuns);
      const loadedScenarioId = savedScenarios.some((item) => item.id === scenarioId)
        ? scenarioId
        : savedScenarios.some((item) => item.id === savedRuns[0]?.scenario_id)
          ? savedRuns[0].scenario_id : savedScenarios[0]?.id ?? '';
      setScenarioId(loadedScenarioId);
      setSelectedRunId(savedRuns.some((item) => item.id === selectedRunId && item.scenario_id === loadedScenarioId)
        ? selectedRunId : savedRuns.find((item) => item.scenario_id === loadedScenarioId)?.id ?? null);
    } catch (cause) {
      setConnected(false);
      setError(`The local simulation service could not be loaded. ${messageOf(cause)}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    setEditor(scenario ? JSON.stringify(scenario, null, 2) : '');
    setSaveMessage(null);
    setEditorError(null);
  }, [scenarioId]);
  useEffect(() => {
    if (importOpen && !dialogRef.current?.open) dialogRef.current?.showModal();
    if (!importOpen && dialogRef.current?.open) dialogRef.current?.close();
  }, [importOpen]);
  useEffect(() => {
    const id = selectedRun?.parent_run_id;
    if (id && !runs.some((run) => run.id === id) && !parentCache[id]) {
      void api<Run>(`/runs/${encodeURIComponent(id)}`).then((run) => setParentCache((old) => ({ ...old, [id]: run }))).catch((cause) => setError(`Could not load the parent comparison: ${messageOf(cause)}`));
    }
  }, [selectedRun, runs, parentCache]);

  function selectScenario(id: string) {
    setScenarioId(id);
    setSelectedRunId(runs.find((run) => run.scenario_id === id)?.id ?? null);
    setHighlightId(null);
    setTimelineTab('conversation');
    setError(null);
  }

  function rememberRun(run: Run) {
    setRuns((old) => [run, ...old.filter((item) => item.id !== run.id)].slice(0, 50));
    setSelectedRunId(run.id);
    setScenarioId(run.scenario_id);
    setPage('workspace');
    setTimelineTab('conversation');
    setHighlightId(null);
  }

  async function runBaseline() {
    if (!scenario || busy) return;
    setBusy('baseline');
    setError(null);
    try { rememberRun(await api<Run>('/runs', { scenario_id: scenario.id })); }
    catch (cause) { setError(messageOf(cause)); }
    finally { setBusy(null); }
  }

  async function refine(suggestion: Suggestion) {
    if (!visibleRun || busy) return;
    setBusy(suggestion.id);
    setError(null);
    try { rememberRun(await api<Run>(`/runs/${encodeURIComponent(visibleRun.id)}/refine`, { suggestion_id: suggestion.id })); }
    catch (cause) { setError(messageOf(cause)); }
    finally { setBusy(null); }
  }

  async function saveConfig() {
    if (busy) return;
    setBusy('save');
    setEditorError(null);
    setSaveMessage(null);
    try {
      const parsed: unknown = JSON.parse(editor);
      const saved = await api<Scenario>('/scenarios', parsed);
      setScenarios((old) => [...old.filter((item) => item.id !== saved.id), saved]);
      setScenarioId(saved.id);
      setEditor(JSON.stringify(saved, null, 2));
      setSaveMessage('Configuration saved to your local workspace. The next baseline run will use it.');
    } catch (cause) { setEditorError(messageOf(cause)); }
    finally { setBusy(null); }
  }

  async function importEmail() {
    if (busy) return;
    if (!importText.trim()) { setImportError('Paste an email or choose a text file first.'); return; }
    if (new TextEncoder().encode(importText).length > 131_072) { setImportError('Email text must be 128 KiB or smaller (UTF-8).'); return; }
    setBusy('import');
    setImportError(null);
    try {
      const imported = await api<Scenario>('/import/email', { text: importText, ...(importName.trim() ? { name: importName.trim() } : {}) });
      setScenarios((old) => [...old.filter((item) => item.id !== imported.id), imported]);
      setScenarioId(imported.id);
      setSelectedRunId(null);
      setImportedIds((old) => [...old, imported.id]);
      setPage('workspace');
      setImportOpen(false);
      setImportText('');
      setImportName('');
    } catch (cause) { setImportError(messageOf(cause)); }
    finally { setBusy(null); }
  }

  function showEvidence(id: string) {
    setTimelineTab('conversation');
    setHighlightId(id);
    setTimeout(() => document.getElementById(`event-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50);
  }

  function exportRun(run: Run) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `innovsim-${run.id}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const navItems: { id: Page; label: string; icon: typeof Activity }[] = [
    { id: 'workspace', label: 'Simulation lab', icon: FlaskConical },
    { id: 'history', label: 'Run history', icon: History },
    { id: 'configuration', label: 'Configuration', icon: Code2 },
    { id: 'guide', label: 'Project guide', icon: FileCode2 },
  ];

  return <div className="app-shell">
    <aside className="sidebar">
      <a className="brand" href="#workspace" onClick={(event) => { event.preventDefault(); setPage('workspace'); }} aria-label="InnovSim home">
        <span className="brand-symbol"><Box size={24} strokeWidth={1.5} /><span /></span>
        <span>Innov<span className="brand-light">Sim</span><small>BY INNOVAD AI SOLUTIONS</small></span>
      </a>
      <div className="workspace-switch"><span className="workspace-letter">S</span><div>Supply chain lab<small>Local workspace</small></div><span className="local-dot" /></div>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Main navigation">{navItems.map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${page === id ? 'active' : ''}`} onClick={() => setPage(id)} aria-current={page === id ? 'page' : undefined}><Icon size={18} />{label}{id === 'history' && <span className="nav-count">{runs.length}</span>}</button>)}</nav>
      <div className="sidebar-bottom">
        <div className="local-card"><span className="local-orbit"><CircleDot size={18} /></span><strong>Your environment.<br />Your agents.</strong><p>Code-first. Self-hosted.<br />Built to be yours.</p><button onClick={() => setPage('guide')}>Explore the project <ArrowUpRight size={14} /></button></div>
        <div className="sidebar-status"><span className={`status-dot ${connected ? 'connected' : ''}`} />{connected ? 'Local service connected' : loading ? 'Connecting to local service' : 'Local service unavailable'}<small>Prototype v0.1</small></div>
      </div>
    </aside>

    <div className="main-shell">
      <header className="topbar"><div className="breadcrumbs"><span>Workspace</span><ChevronRight size={14} /><strong>{navItems.find((item) => item.id === page)?.label}</strong></div><div className="topbar-right"><span className="mode-badge"><span />Offline deterministic demo</span><span className="avatar" aria-label="Innovad AI Solutions">IA</span></div></header>
      <main>
        {error && <div className="notice error" role="alert"><Info size={18} /><div><strong>Something needs attention</strong><p>{error}</p></div><button onClick={() => { if (!connected) void load(); else setError(null); }}>{!connected ? 'Retry connection' : 'Dismiss'}</button></div>}
        {loading && !scenario ? <div className="loading-state"><LoaderCircle className="spin" size={26} /><h2>Opening your workspace</h2><p>Loading local scenarios and saved runs.</p></div> : <>
          {page === 'workspace' && <>
            <div className="page-heading"><div><div className="eyebrow"><span />SIMULATE. OBSERVE. REFINE.</div><h1>Better agents. <span>Better together.</span></h1><p>A safe place to see how your business agents work as a system.</p></div><button className="button secondary" onClick={() => { setImportError(null); setImportOpen(true); }} disabled={!connected}><Mail size={16} />Import email</button></div>
            {scenario ? <>
              <section className="scenario-bar" aria-label="Scenario controls"><div className="scenario-selector"><label htmlFor="scenario-select">SCENARIO</label><div><FlaskConical size={18} /><select id="scenario-select" value={scenarioId} onChange={(event) => selectScenario(event.target.value)}>{scenarios.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><ChevronDown size={15} /></div></div><div className="scenario-properties"><span><CircleDot size={14} />{scenario.domain}</span><span><GitBranch size={14} />Seed {scenario.seed}</span><span><Bot size={14} />{scenario.agents.filter((agent) => agent.enabled).length} active agents</span></div><button className="button primary" onClick={() => void runBaseline()} disabled={!!busy || !connected}>{busy === 'baseline' ? <LoaderCircle className="spin" size={16} /> : <Play size={15} fill="currentColor" />}Run baseline</button></section>
              {importedIds.includes(scenario.id) && <div className="notice info"><Mail size={18} /><div><strong>Email imported as local text</strong><p>This scenario uses the email as its opening message and the supplier-delay fixture for its world. No mailbox was connected.</p></div></div>}
              <div className="simulation-grid">
                <section className="panel agent-panel"><div className="panel-heading"><div><h2>Agent network</h2><p>{visibleRun ? 'Immutable configuration tested in this run.' : 'Independent agents. One shared workflow.'}</p></div><span className="small-badge"><span className="status-dot connected" />Simulated tools</span></div><div className="network-canvas"><div className="network-grid">{displayedScenario!.agents.map((agent, index) => <div key={agent.id} className={`agent-node color-${index % 4} ${!agent.enabled ? 'disabled' : ''}`}><div className="agent-node-top"><span className="agent-icon"><AgentIcon agent={agent} /></span><span className={`agent-state ${agent.enabled ? '' : 'off'}`}>{agent.enabled ? 'Ready' : 'Disabled'}</span></div><h3>{agent.name}</h3><p>{agent.company}</p><div className="agent-role">{agent.role}</div><div className="agent-foot"><span>{agent.skills.length} skills</span><span>{agent.tools.length} tools</span></div><span className="agent-port" /></div>)}</div><div className="network-caption"><span className="network-line" /><span>Messages & tool calls</span><ArrowRight size={12} /><span>Traceable outcomes</span></div></div><div className="network-footer"><Info size={14} /><span>Deterministic agents run locally. All business tools are simulated.</span><button onClick={() => setPage('configuration')}>Edit configuration <ArrowUpRight size={13} /></button></div></section>
                <section className="panel briefing-panel"><div className="panel-heading"><div><h2>The scenario</h2><p>{visibleRun ? 'World and message used by this run.' : 'Start with a real business question.'}</p></div><MessageSquare size={18} /></div><p className="scenario-description">{displayedScenario!.description}</p><div className="incoming-message"><div><Mail size={14} />OPENING MESSAGE</div><p>{displayedScenario!.initial_message}</p></div><div className="world-summary"><div><span>Order quantity</span><strong>{number.format(displayedScenario!.world.order_quantity)}</strong></div><div><span>Available stock</span><strong>{number.format(displayedScenario!.world.available_stock)}</strong></div><div><span>Supply delay</span><strong>{displayedScenario!.world.delay_days} days</strong></div><div><span>Budget limit</span><strong>{number.format(displayedScenario!.world.budget_limit)}</strong></div></div></section>
              </div>
              {visibleRun ? <>
                <div className="section-heading run-section-heading"><div><h2>Run results <span className={`variant ${visibleRun.variant}`}>{visibleRun.variant}</span></h2><p>{date(visibleRun.created_at)} <span>·</span> Same scenario, reproducible seed {visibleRun.seed}</p></div><div className="run-header-actions"><label className="sr-only" htmlFor="run-select">Select saved run</label><select id="run-select" value={visibleRun.id} onChange={(event) => setSelectedRunId(event.target.value)}>{scenarioRuns.map((run) => <option value={run.id} key={run.id}>{run.variant === 'baseline' ? 'Baseline' : 'Candidate'} · {date(run.created_at)} · {run.id.slice(-6)}</option>)}</select><button className="icon-button" aria-label="Download this run as JSON" title="Download run JSON" onClick={() => exportRun(visibleRun)}><ArrowDownToLine size={18} /></button></div></div>
                {visibleRun.parent_run_id && <div className="comparison-note"><GitCompareArrows size={18} /><div><strong>Candidate comparison</strong><span>Compared with its parent run using the same scenario, seed and saved configuration plus the selected patch.</span></div>{parent && <button onClick={() => setSelectedRunId(parent.id)}>View parent <ArrowUpRight size={14} /></button>}</div>}
                <div className="metrics-grid"><Metric icon={Activity} label="Outcome score" value={`${visibleRun.metrics.score}`} suffix="/ 100" delta={parent ? visibleRun.metrics.score - parent.metrics.score : undefined} goodWhen="up" caption={visibleRun.metrics.goal_success ? 'Business goal achieved' : 'Business goal needs work'} emphasis /><Metric icon={MessageSquare} label="Conversation turns" value={number.format(visibleRun.metrics.turns)} delta={parent ? visibleRun.metrics.turns - parent.metrics.turns : undefined} goodWhen="down" caption={`${visibleRun.metrics.tool_calls} simulated tool calls`} /><Metric icon={Wallet} label="Hypothetical cost" value={number.format(visibleRun.metrics.cost)} delta={parent ? visibleRun.metrics.cost - parent.metrics.cost : undefined} goodWhen="down" caption="Business spend · fixture units" /><Metric icon={Clock3} label="Simulated time" value={number.format(visibleRun.metrics.simulated_minutes)} suffix="min" delta={parent ? visibleRun.metrics.simulated_minutes - parent.metrics.simulated_minutes : undefined} goodWhen="down" caption="Fixture estimate · not runtime" /></div>
                <div className="results-grid"><section className="panel timeline-panel"><div className="timeline-tabs" role="tablist" aria-label="Run evidence"><button role="tab" aria-selected={timelineTab === 'conversation'} className={timelineTab === 'conversation' ? 'selected' : ''} onClick={() => setTimelineTab('conversation')}><MessageSquare size={16} />Conversation <span>{visibleRun.events.length}</span></button><button role="tab" aria-selected={timelineTab === 'checks'} className={timelineTab === 'checks' ? 'selected' : ''} onClick={() => setTimelineTab('checks')}><ShieldCheck size={16} />Business checks <span>{visibleRun.checks.length}</span></button><div className="trace-label"><span className="status-dot connected" />Full trace</div></div>{timelineTab === 'conversation' ? <div className="timeline" role="tabpanel" aria-label="Conversation trace">{visibleRun.events.length ? visibleRun.events.map((event) => <EventCard key={event.id} event={event} highlighted={highlightId === event.id} />) : <div className="empty-compact">This run returned no events.</div>}</div> : <div className="checks-list" role="tabpanel" aria-label="Business checks">{visibleRun.checks.length ? visibleRun.checks.map((check) => <div className={`check-card ${check.passed ? 'passed' : 'failed'}`} key={check.id}><span className="check-icon">{check.passed ? <CheckCircle2 size={18} /> : <Info size={18} />}</span><div><div className="check-title"><h3>{check.name}</h3><span>{check.passed ? 'Passed' : 'Needs attention'}</span></div><p>{check.evidence}</p><div className="evidence-links">{check.event_ids.map((id) => <button key={id} onClick={() => showEvidence(id)}>View evidence <ArrowUpRight size={12} /></button>)}</div></div></div>) : <div className="empty-compact">This run returned no business checks.</div>}</div>}<details className="snapshot"><summary><Code2 size={14} />Immutable run configuration <ChevronDown size={14} /></summary><pre>{JSON.stringify(visibleRun.configuration, null, 2)}</pre></details></section><section className="refinements-panel"><div className="section-heading"><div><h2><Sparkles size={18} />Refinement ideas</h2><p>Small changes. Measurable outcomes.</p></div><span className="suggestion-count">{visibleRun.suggestions.length}</span></div><div className="refinement-note"><Info size={14} /><span>Rule-based suggestions from this trace. Apply one to create and compare a candidate.</span></div>{visibleRun.suggestions.length ? visibleRun.suggestions.map((suggestion) => <article className="suggestion-card" key={suggestion.id}><div className="suggestion-type"><Wrench size={13} />{suggestion.kind.replaceAll('_', ' ')}</div><h3>{suggestion.title}</h3><p>{suggestion.rationale}</p><div className="evidence-links">{suggestion.evidence_event_ids.map((id) => <button key={id} onClick={() => showEvidence(id)}>Evidence {visibleRun.events.find((event) => event.id === id)?.step ?? ''}<ArrowUpRight size={12} /></button>)}</div><details className="patch"><summary>Inspect suggested patch <ChevronDown size={12} /></summary><pre>{JSON.stringify(suggestion.patch, null, 2)}</pre></details><button className="apply-button" onClick={() => void refine(suggestion)} disabled={!!busy}>{busy === suggestion.id ? <LoaderCircle className="spin" size={15} /> : <Plus size={15} />}Apply & compare <ArrowRight size={15} /></button></article>) : <div className="no-suggestions"><CheckCircle2 size={25} /><h3>No further suggestions</h3><p>The demo rules found no additional changes for this run. Review its business checks and trace.</p></div>}</section></div>
              </> : <div className="empty-run"><div className="empty-run-icon"><Play size={20} /></div><div><h2>Your first run starts here.</h2><p>Run the scenario to inspect the conversation, check the outcome, and discover refinements.</p></div><button className="text-button" onClick={() => void runBaseline()} disabled={!!busy || !connected}>Run baseline <ArrowRight size={16} /></button></div>}
            </> : <div className="empty-run"><FlaskConical size={28} /><div><h2>No scenarios loaded</h2><p>Start the local backend and retry to load the demonstration scenario.</p></div><button className="button secondary" onClick={() => void load()}>Retry <RotateCcw size={15} /></button></div>}
            <div className="page-footnote"><ShieldCheck size={14} />A simulation environment. No emails are sent, live systems changed, or model APIs called.</div>
          </>}

          {page === 'history' && <><div className="page-heading"><div><div className="eyebrow">OBSERVE THE DIFFERENCE</div><h1>Every run. <span>Every iteration.</span></h1><p>Your persisted local history, including baseline and candidate comparisons.</p></div><button className="button secondary" onClick={() => void load()} disabled={loading}><RotateCcw size={16} />Refresh</button></div><section className="panel history-panel"><div className="panel-heading"><div><h2>Run history</h2><p>Showing the most recent {runs.length} runs. The service keeps the latest 50.</p></div><History size={18} /></div>{runs.length ? <div className="table-wrap"><table><thead><tr><th>Scenario / run</th><th>Variant</th><th>Score</th><th>Outcome</th><th>Created</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>{runs.map((run) => <tr key={run.id}><td><button className="history-run-link" onClick={() => { setScenarioId(run.scenario_id); setSelectedRunId(run.id); setPage('workspace'); }}><strong>{run.scenario_name}</strong><small>{run.id}</small></button></td><td><span className={`variant ${run.variant}`}>{run.variant}</span>{run.parent_run_id && <small className="parent-label">Parent {run.parent_run_id.slice(-6)}</small>}</td><td><strong className="table-score">{run.metrics.score}</strong><span className="muted"> / 100</span></td><td><span className={`outcome-pill ${run.metrics.goal_success ? 'success' : ''}`}>{run.metrics.goal_success ? 'Achieved' : 'Needs work'}</span></td><td className="date-cell">{date(run.created_at)}</td><td><button className="icon-button" onClick={() => exportRun(run)} aria-label={`Download run ${run.id}`}><ArrowDownToLine size={17} /></button></td></tr>)}</tbody></table></div> : <div className="large-empty"><History size={30} /><h2>A clean slate</h2><p>Run your first scenario and it will appear here.</p><button className="button primary" onClick={() => setPage('workspace')}>Open simulation lab <ArrowRight size={15} /></button></div>}</section></>}

          {page === 'configuration' && <><div className="page-heading"><div><div className="eyebrow">CODE-FIRST BY DESIGN</div><h1>Make it <span>your system.</span></h1><p>Edit the scenario, agents, skills, tools and world as raw configuration.</p></div><button className="button primary" onClick={() => void saveConfig()} disabled={!scenario || !!busy || !dirty}>{busy === 'save' ? <LoaderCircle className="spin" size={16} /> : <Check size={16} />}Save configuration</button></div><div className="notice info"><Terminal size={18} /><div><strong>Deterministic adapter</strong><p>Prompt edits are recorded in each run. This demo's behavior is controlled by supported skills and mock tools, so changing prompt text does not change its decisions. No arbitrary code is executed.</p></div></div>{editorError && <div className="notice error" role="alert"><Info size={18} /><div><strong>Configuration could not be saved</strong><pre>{editorError}</pre></div></div>}{saveMessage && <div className="notice success" role="status"><CheckCircle2 size={18} /><p>{saveMessage}</p></div>}{scenario && <section className="panel editor-panel"><div className="panel-heading"><div><h2>Scenario configuration <span className={`edit-state ${dirty ? 'unsaved' : ''}`}>{dirty ? 'Unsaved changes' : 'Saved'}</span></h2><label className="sr-only" htmlFor="config-scenario">Configuration scenario</label><select id="config-scenario" value={scenarioId} onChange={(event) => selectScenario(event.target.value)}>{scenarios.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div><button className="text-button" onClick={() => { setEditor(savedJSON); setEditorError(null); setSaveMessage(null); }} disabled={!dirty || !!busy}><RotateCcw size={14} />Reset changes</button></div><div className="editor-file"><Code2 size={15} /><span>{scenario.id}.json</span><span>JSON</span></div><label className="sr-only" htmlFor="configuration-json">Edit scenario JSON</label><textarea id="configuration-json" className="json-editor" value={editor} onChange={(event) => { setEditor(event.target.value); setSaveMessage(null); }} spellCheck={false} aria-describedby="config-help" /><div className="editor-bottom" id="config-help"><Info size={14} />Save validates the complete scenario on the local API. Existing runs keep an immutable snapshot.</div></section>}<div className="configuration-cards"><div className="panel"><Wrench size={22} /><h3>Skills & tools</h3><p>Skill and tool names are adapter-specific. See the project guide and backend source for capabilities this demo implements.</p><button className="text-button" onClick={() => setPage('guide')}>Read the project guide <ArrowUpRight size={14} /></button></div><div className="panel"><GitBranch size={22} /><h3>Reproducible comparisons</h3><p>A refinement runs against its parent's snapshot with the same seed. Saving the editor changes the next baseline, independently of candidate runs.</p></div></div></>}

          {page === 'guide' && <><div className="page-heading"><div><div className="eyebrow">OPEN BY DESIGN</div><h1>Your agents. <span>Your infrastructure.</span></h1><p>A code-first foundation for exploring how business agents collaborate.</p></div></div><div className="guide-hero panel"><div className="guide-mark"><Box size={35} strokeWidth={1.25} /></div><div><span className="guide-tag">INNOVSIM / LOCAL PROTOTYPE</span><h2>Build confidence before connecting production.</h2><p>Simulate a workflow, read the evidence, apply a small refinement, and compare the result. The current prototype runs deterministic Python agents with mock tools and a React workbench.</p></div></div><div className="guide-grid"><section className="panel guide-section"><h2>Try the complete loop</h2><ol><li><span>01</span><div><h3>Choose a scenario</h3><p>Review its opening message, agents and world. You can import plain email text or a .eml file as a new scenario.</p></div></li><li><span>02</span><div><h3>Run and observe</h3><p>Run a baseline. Inspect every message and tool call, then check the business outcome and constraints.</p></div></li><li><span>03</span><div><h3>Refine with evidence</h3><p>Inspect a suggested patch and apply it. The new candidate links to its parent and shows metric deltas.</p></div></li><li><span>04</span><div><h3>Make your own changes</h3><p>Edit the JSON configuration, save it, and run another baseline. Download any complete run for review.</p></div></li></ol><button className="button primary" onClick={() => setPage('workspace')}>Open simulation lab <ArrowRight size={15} /></button></section><div className="guide-right"><section className="panel guide-section"><h2>What runs here today</h2><div className="capability"><CheckCircle2 size={17} /><span>Local deterministic simulation</span></div><div className="capability"><CheckCircle2 size={17} /><span>Persisted scenarios and run traces</span></div><div className="capability"><CheckCircle2 size={17} /><span>Evidence-linked rule suggestions</span></div><div className="capability"><CheckCircle2 size={17} /><span>Same-seed parent comparisons</span></div><div className="capability"><CheckCircle2 size={17} /><span>Plain text / .eml import</span></div></section><section className="panel guide-section future-section"><h2>Extension points</h2><p>Live mailbox connectors, remote agents, model-backed counterparts, MCP/A2A adapters and automated code refinement are future integrations. They are not connected by this demo.</p><div className="guide-code"><Terminal size={15} />Bring your code. Keep your control.</div></section></div></div><div className="guide-bottom panel"><div><Code2 size={23} /><div><h3>Explore the source</h3><p>Architecture, research and setup instructions live in the project repository.</p></div></div><a className="button secondary" href="https://github.com/innovadaisolutions/InnovSim" target="_blank" rel="noreferrer">Open repository <ArrowUpRight size={15} /></a></div></>}
        </>}
      </main>
    </div>

    <dialog ref={dialogRef} className="import-dialog" onCancel={() => setImportOpen(false)} onClick={(event) => { if (event.target === dialogRef.current && !busy) setImportOpen(false); }}><div className="dialog-heading"><div><div className="eyebrow">FROM EMAIL TO SCENARIO</div><h2>Bring a conversation into the lab.</h2></div><button className="icon-button" aria-label="Close email import" onClick={() => setImportOpen(false)} disabled={busy === 'import'}><X size={20} /></button></div><p className="dialog-intro">Import email text as the opening message for a new supplier-delay scenario. This stays in your local workspace.</p><div className="notice info"><Mail size={17} /><p>Local text import. No account connection, mailbox access or email sending.</p></div><label htmlFor="import-name">Scenario name <span>(optional)</span></label><input id="import-name" maxLength={160} value={importName} onChange={(event) => setImportName(event.target.value)} placeholder="e.g. October supplier delay" /><label htmlFor="email-text">Email text</label><textarea id="email-text" value={importText} onChange={(event) => setImportText(event.target.value)} placeholder="Paste the email body, or the full .eml content…" rows={8} /><div className="file-import"><label htmlFor="email-file"><Plus size={14} />Choose a .eml or .txt file</label><input id="email-file" type="file" accept=".eml,.txt,text/plain,message/rfc822" onChange={async (event) => { const file = event.target.files?.[0]; if (file) { if (file.size > 131_072) { setImportError('Choose an email file no larger than 128 KiB.'); return; } setImportText(await file.text()); if (!importName) setImportName(file.name.replace(/\.(eml|txt)$/i, '')); setImportError(null); } }} /><span>Up to 128 KiB</span></div>{importError && <p className="inline-error" role="alert">{importError}</p>}<div className="dialog-footer"><button className="button secondary" onClick={() => setImportOpen(false)} disabled={busy === 'import'}>Cancel</button><button className="button primary" onClick={() => void importEmail()} disabled={!!busy}>{busy === 'import' ? <LoaderCircle className="spin" size={16} /> : <ArrowRight size={16} />}Create local scenario</button></div></dialog>
  </div>;
}

function Metric({ icon: Icon, label, value, suffix, caption, delta, goodWhen, emphasis }: { icon: typeof Activity; label: string; value: string; suffix?: string; caption: string; delta?: number; goodWhen: 'up' | 'down'; emphasis?: boolean }) {
  return <div className={`metric-card ${emphasis ? 'emphasis' : ''}`}><div className="metric-label"><span>{label}</span><Icon size={17} /></div><div className="metric-value">{value}<small>{suffix}</small>{delta !== undefined && <span className={`metric-delta ${delta === 0 ? 'neutral' : (goodWhen === 'up' ? delta > 0 : delta < 0) ? 'positive' : 'negative'}`} aria-label={`${delta >= 0 ? '+' : ''}${delta} compared with parent`}>{delta > 0 ? <ArrowUpRight size={12} /> : delta < 0 ? <ArrowDown size={12} /> : null}{delta > 0 ? '+' : ''}{number.format(delta)}</span>}</div><p>{caption}</p></div>;
}

function EventCard({ event, highlighted }: { event: RunEvent; highlighted: boolean }) {
  const Icon = event.kind === 'tool' ? Wrench : event.kind === 'check' ? ShieldCheck : event.kind === 'system' ? Terminal : Bot;
  return <article id={`event-${event.id}`} className={`event-card ${event.kind} ${highlighted ? 'highlighted' : ''}`} tabIndex={highlighted ? 0 : undefined}><div className="event-avatar"><Icon size={17} /></div><div className="event-body"><div className="event-heading"><strong>{event.agent_name || 'System'}</strong>{event.recipient && <><ArrowRight size={12} /><span>{event.recipient}</span></>}<span className="event-step">#{event.step}</span></div><div className="event-kind">{event.kind === 'tool' ? <><Wrench size={11} />{event.tool_name || 'Tool call'}</> : event.kind !== 'message' ? event.kind : 'Message'}</div><p>{event.content}</p>{event.data && Object.keys(event.data).length > 0 && <details className="event-data"><summary>Tool / event data <ChevronDown size={12} /></summary><pre>{JSON.stringify(event.data, null, 2)}</pre></details>}</div></article>;
}

export default App;
