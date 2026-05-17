import {
  Activity,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  Code2,
  Database,
  Download,
  FileText,
  Globe2,
  Loader2,
  Map as MapIcon,
  Search,
  Server,
  Sparkles,
  Terminal,
  TriangleAlert
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  explainVariable,
  getDataset,
  getHealth,
  getVariables,
  indexLocal,
  resolveDataset,
  skillUrl
} from "./api";
import type { DatasetPage, HealthResponse, VariableExplainResponse, VariableInventory, VariableRecord } from "./types";

type LoadState = "idle" | "loading" | "ready" | "error";

function routeDatasetId(): string | null {
  const match = window.location.pathname.match(/^\/data\/dandi_(\d{6})/);
  return match?.[1] ?? null;
}

function routeIsDocs(): boolean {
  return window.location.pathname === "/docs";
}

export function App() {
  const [datasetId, setDatasetId] = useState<string | null>(() => routeDatasetId());
  const [docsOpen, setDocsOpen] = useState(() => routeIsDocs());
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  const navigate = (id: string) => {
    window.history.pushState({}, "", `/data/dandi_${id}`);
    setDocsOpen(false);
    setDatasetId(id);
  };

  const openDocs = () => {
    window.history.pushState({}, "", "/docs");
    setDatasetId(null);
    setDocsOpen(true);
  };

  useEffect(() => {
    const onPop = () => {
      setDatasetId(routeDatasetId());
      setDocsOpen(routeIsDocs());
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  return (
    <div className="app-shell">
      <TopBar health={health} onHome={() => navigateHome(setDatasetId, setDocsOpen)} onDocs={openDocs} />
      {datasetId ? <DatasetView datasetId={datasetId} /> : docsOpen ? <Documentation /> : <Landing onNavigate={navigate} health={health} />}
    </div>
  );
}

function navigateHome(setDatasetId: (value: string | null) => void, setDocsOpen: (value: boolean) => void) {
  window.history.pushState({}, "", "/");
  setDatasetId(null);
  setDocsOpen(false);
}

function TopBar({ health, onHome, onDocs }: { health: HealthResponse | null; onHome: () => void; onDocs: () => void }) {
  const ready = health?.llm.status === "ready";
  return (
    <header className="topbar">
      <button className="brand-button" onClick={onHome} aria-label="Go to home">
        <BrainCircuit size={23} />
        <span>Neurodata Without Barriers</span>
      </button>
      <div className="topbar-actions">
        <button className="docs-button" onClick={onDocs}>
          <BookOpen size={16} />
          <span>Docs</span>
        </button>
        <div className={ready ? "status-pill good" : "status-pill warn"} title={health?.llm.base_url ?? "Checking local LLM"}>
          {ready ? <CheckCircle2 size={16} /> : <TriangleAlert size={16} />}
          <span>{ready ? health?.llm.model ?? "Local LLM ready" : "LLM checking"}</span>
        </div>
      </div>
    </header>
  );
}

function Landing({ onNavigate, health }: { onNavigate: (datasetId: string) => void; health: HealthResponse | null }) {
  const [value, setValue] = useState("");
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const llmLabel =
    health?.llm.status === "ready"
      ? health.llm.model
      : health?.llm.base_url
        ? `checking ${health.llm.base_url}`
        : "not configured";

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setState("loading");
    setError(null);
    try {
      const result = await resolveDataset(value);
      onNavigate(result.dataset_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not resolve dataset.");
      setState("error");
    }
  };

  return (
    <main className="landing">
      <section className="landing-copy">
        <div className="eyebrow">
          <Sparkles size={16} />
          <span>DANDI explorer powered by your local model</span>
        </div>
        <h1>Neurodata Without Barriers</h1>
        <p className="tagline">Where centuries of research data come alive.</p>
        <form className="resolver" onSubmit={submit}>
          <Search size={20} />
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Paste a DANDI URL or ID, e.g. 001097"
            aria-label="DANDI dataset URL or ID"
          />
          <button type="submit" disabled={state === "loading"}>
            {state === "loading" ? <Loader2 size={18} className="spin" /> : <ArrowRight size={18} />}
            <span>Explore</span>
          </button>
        </form>
        {error ? <p className="inline-error">{error}</p> : null}
        <div className="quick-row">
          <button onClick={() => onNavigate("001097")}>
            <Database size={17} />
            <span>Open DANDI example 001097</span>
          </button>
          <div className="quiet-note">
            LLM: {llmLabel}
          </div>
        </div>
      </section>
      <section className="landing-visual" aria-label="Dataset flow preview">
        <div className="flow-row">
          <FlowNode icon={<Database size={19} />} label="DANDI metadata" active />
          <FlowNode icon={<Activity size={19} />} label="NWB variables" active />
          <FlowNode icon={<Sparkles size={19} />} label="Local LLM" active={health?.llm.status === "ready"} />
        </div>
        <div className="preview-panel">
          <SkeletonLine width="55%" />
          <SkeletonLine width="88%" />
          <SkeletonLine width="72%" />
          <div className="mini-map">
            {Array.from({ length: 18 }).map((_, index) => (
              <span key={index} className={index % 4 === 0 ? "node warm" : index % 3 === 0 ? "node blue" : "node green"} />
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function Documentation() {
  return (
    <main className="docs-page">
      <section className="docs-hero">
        <div>
          <div className="eyebrow">
            <BookOpen size={16} />
            <span>Documentation</span>
          </div>
          <h1>Run the browser explorer, MCP servers, and local data tools from one suite.</h1>
          <p>
            The project is built around a hostable web app plus Model Context Protocol servers for DANDI,
            OpenNeuro, and IBL. Public archive metadata can be explored immediately; local data stays on the
            machine or runtime volume where the app indexes it.
          </p>
        </div>
      </section>

      <section className="docs-grid">
        <DocCard icon={<Globe2 size={22} />} title="Web Explorer">
          <p>React + FastAPI interface for resolving DANDI IDs, reading archive metadata, mapping NWB variables, indexing local Dandiset paths, and exporting dataset-specific skills.</p>
          <CodeSnippet value={"docker compose -f docker-compose.web.yml up --build"} />
        </DocCard>
        <DocCard icon={<Server size={22} />} title="MCP Servers">
          <p>DANDI, OpenNeuro, and IBL servers expose provider-native discovery tools plus a shared local dataset explorer API for agent workflows.</p>
          <CodeSnippet value={"python harness/generate_mcp_config.py --format mcp-json"} />
        </DocCard>
        <DocCard icon={<Database size={22} />} title="Data Policy">
          <p>NWB files, downloaded samples, generated figures, local cache, and session recordings are ignored by git. Commit code, docs, configs, and reproducible hosting assets only.</p>
          <CodeSnippet value={"NEURODATA_MCP_STORAGE_DIR=/data/.mcp-storage"} />
        </DocCard>
        <DocCard icon={<Terminal size={22} />} title="Local Development">
          <p>Run the backend and frontend separately while building. Use an OpenAI-compatible model endpoint when AI summaries are desired.</p>
          <CodeSnippet value={"cd web-app/backend && uv run --extra analysis uvicorn neurodata_web.main:app --reload --port 8787"} />
        </DocCard>
      </section>

      <section className="docs-section">
        <div className="section-title">
          <h2>Suite Map</h2>
          <span>What is included</span>
        </div>
        <div className="suite-table">
          <SuiteRow name="DANDI MCP" path="dandi-mcp-server" detail="Dandisets, versions, assets, download URLs, NWB/Zarr inspection, NWB validation, signal inventory, and literature-aware variable explanation." />
          <SuiteRow name="OpenNeuro MCP" path="openneuro-mcp-server" detail="OpenNeuro search, BIDS metadata, participants, tasks, events, derivatives, local BIDS indexing, and semantic discovery." />
          <SuiteRow name="IBL MCP" path="ibl-mcp-server" detail="OpenAlyx sessions, datasets, subjects, insertions, channels, behavior summaries, ecephys metadata, and local ALF-style indexing." />
          <SuiteRow name="Web App" path="web-app" detail="Browser workflow for DANDI dataset pages, local NWB indexing, variable maps, AI summaries, skill export, and single-container hosting." />
          <SuiteRow name="Harness" path="harness" detail="Utilities for checking server entry points and generating MCP client configuration for agent environments." />
          <SuiteRow name="Docs Site" path="docs" detail="MkDocs guide set covering installation, shared explorer workflows, provider-specific servers, compatibility, and development." />
        </div>
      </section>

      <section className="docs-section two-column-docs">
        <div>
          <h2>Hosting Checklist</h2>
          <p>Copy `web-app/.env.example` only when you need overrides. Compose works without a checked-in `.env`, serves the built frontend from FastAPI, and keeps runtime state in a Docker volume.</p>
        </div>
        <div>
          <h2>Split Hosting</h2>
          <p>Build the frontend with `VITE_API_BASE_URL=https://your-api-host` and set `NEURODATA_CORS_ORIGINS` on the backend to the exact frontend origin.</p>
        </div>
      </section>
    </main>
  );
}

function DocCard({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <article className="doc-card">
      <div className="doc-card-title">
        {icon}
        <h2>{title}</h2>
      </div>
      {children}
    </article>
  );
}

function CodeSnippet({ value }: { value: string }) {
  return <pre className="inline-code-snippet">{value}</pre>;
}

function SuiteRow({ name, path, detail }: { name: string; path: string; detail: string }) {
  return (
    <div className="suite-row">
      <div>
        <strong>{name}</strong>
        <span>{path}</span>
      </div>
      <p>{detail}</p>
    </div>
  );
}

function DatasetView({ datasetId }: { datasetId: string }) {
  const [dataset, setDataset] = useState<DatasetPage | null>(null);
  const [variables, setVariables] = useState<VariableInventory | null>(null);
  const [selected, setSelected] = useState<VariableRecord | null>(null);
  const [explanation, setExplanation] = useState<VariableExplainResponse | null>(null);
  const [datasetState, setDatasetState] = useState<LoadState>("loading");
  const [variableState, setVariableState] = useState<LoadState>("loading");
  const [explainState, setExplainState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [localPath, setLocalPath] = useState("");
  const [indexing, setIndexing] = useState(false);
  const [indexMessage, setIndexMessage] = useState<string | null>(null);

  useEffect(() => {
    setDataset(null);
    setVariables(null);
    setSelected(null);
    setExplanation(null);
    setDatasetState("loading");
    setVariableState("loading");
    setError(null);
    getDataset(datasetId)
      .then((data) => {
        setDataset(data);
        setDatasetState("ready");
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Dataset failed to load.");
        setDatasetState("error");
      });
    getVariables(datasetId)
      .then((data) => {
        setVariables(data);
        setVariableState("ready");
      })
      .catch(() => setVariableState("error"));
  }, [datasetId]);

  const filteredVariables = useMemo(() => {
    const rows = variables?.variables ?? [];
    const q = query.toLowerCase();
    if (!q) return rows;
    return rows.filter((row) => JSON.stringify(row).toLowerCase().includes(q));
  }, [variables, query]);

  const selectVariable = async (variable: VariableRecord) => {
    setSelected(variable);
    setExplanation(null);
    setExplainState("loading");
    try {
      const result = await explainVariable(datasetId, variable);
      setExplanation(result);
      setExplainState("ready");
    } catch (err) {
      setExplanation({
        dataset_id: datasetId,
        variable: variableName(variable),
        loading_code: "",
        explanation: err instanceof Error ? err.message : "Variable explanation failed.",
        evidence: [],
        context: variable,
        confidence_label: "unknown",
        ai_status: "error"
      });
      setExplainState("error");
    }
  };

  const runIndex = async () => {
    setIndexing(true);
    setIndexMessage("Inspecting local files. NWB parsing can take a moment.");
    try {
      const result = await indexLocal(datasetId, localPath);
      setIndexMessage(String((result as { message?: string }).message ?? `Index status: ${(result as { status?: string }).status}`));
      const next = await getVariables(datasetId);
      setVariables(next);
    } catch (err) {
      setIndexMessage(err instanceof Error ? err.message : "Local indexing failed.");
    } finally {
      setIndexing(false);
    }
  };

  return (
    <main className="dataset-layout">
      <section className="dataset-main">
        {datasetState === "loading" ? <DatasetLoading /> : null}
        {datasetState === "error" ? <ErrorPanel message={error ?? "Dataset failed to load."} /> : null}
        {dataset ? (
          <>
            <DatasetHeader dataset={dataset} />
            <Overview dataset={dataset} />
            <LocalIndexPanel
              localPath={localPath}
              setLocalPath={setLocalPath}
              indexing={indexing}
              indexMessage={indexMessage}
              onIndex={runIndex}
            />
            <VariableMap variables={filteredVariables} loading={variableState === "loading"} onSelect={selectVariable} />
          </>
        ) : null}
      </section>
      <aside className="dataset-side">
        <div className="side-toolbar">
          <label className="search-box">
            <Search size={17} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter variables" />
          </label>
          <a className="icon-action" href={skillUrl(datasetId)} title="Download dataset skill">
            <Download size={18} />
            <span>Skill</span>
          </a>
        </div>
        <VariableList
          variables={filteredVariables}
          loading={variableState === "loading"}
          selected={selected}
          onSelect={selectVariable}
          message={variables?.message}
        />
        <VariableDetail selected={selected} explanation={explanation} state={explainState} />
      </aside>
    </main>
  );
}

function DatasetHeader({ dataset }: { dataset: DatasetPage }) {
  const title = String(dataset.summary.name ?? `DANDI ${dataset.dataset_id}`);
  return (
    <section className="dataset-header">
      <div>
        <p className="dataset-kicker">DANDI {dataset.dataset_id}</p>
        <h1>{title}</h1>
        <div className="fact-row">
          <span><Database size={15} /> {numberish(dataset.assets.count)} assets</span>
          <span><FileText size={15} /> {dataset.papers.length} paper links</span>
          <span><BrainCircuit size={15} /> {dataset.ai_status === "ready" ? "AI overview ready" : "AI unavailable"}</span>
        </div>
      </div>
      <a className="primary-link" href={String(dataset.summary.url ?? `https://dandiarchive.org/dandiset/${dataset.dataset_id}`)} target="_blank" rel="noreferrer">
        <ArrowRight size={18} />
        <span>DANDI</span>
      </a>
    </section>
  );
}

function Overview({ dataset }: { dataset: DatasetPage }) {
  return (
    <section className="overview-grid">
      <div className="overview-copy">
        <h2>Overview</h2>
        {dataset.ai_overview ? <Markdown text={dataset.ai_overview} /> : <MutedNotice text={dataset.ai_error ?? "The local model did not return an overview yet."} />}
      </div>
      <div className="metadata-panel">
        <h2>Dataset Facts</h2>
        <Fact label="License" value={dataset.summary.license} />
        <Fact label="Version" value={dataset.version} />
        <Fact label="Citation" value={dataset.summary.citation} />
        <Fact label="Keywords" value={dataset.summary.keywords} />
      </div>
    </section>
  );
}

function LocalIndexPanel({
  localPath,
  setLocalPath,
  indexing,
  indexMessage,
  onIndex
}: {
  localPath: string;
  setLocalPath: (value: string) => void;
  indexing: boolean;
  indexMessage: string | null;
  onIndex: () => void;
}) {
  return (
    <section className="index-panel">
      <div>
        <h2>Local NWB Index</h2>
        <p>Paste a local Dandiset path to unlock object paths, shapes, rates, units, and richer variable explanations.</p>
      </div>
      <div className="index-controls">
        <input value={localPath} onChange={(event) => setLocalPath(event.target.value)} placeholder="/absolute/path/to/dandiset" />
        <button onClick={onIndex} disabled={!localPath || indexing}>
          {indexing ? <Loader2 size={17} className="spin" /> : <MapIcon size={17} />}
          <span>{indexing ? "Indexing" : "Index"}</span>
        </button>
      </div>
      {indexMessage ? <p className="quiet-note">{indexMessage}</p> : null}
    </section>
  );
}

function VariableMap({ variables, loading, onSelect }: { variables: VariableRecord[]; loading: boolean; onSelect: (v: VariableRecord) => void }) {
  const groups = useMemo(() => groupVariables(variables), [variables]);
  return (
    <section className="variable-map-section">
      <div className="section-title">
        <h2>Variable Map</h2>
        <span>{loading ? "Loading" : `${variables.length} variables`}</span>
      </div>
      {loading ? <MapLoading /> : null}
      {!loading && variables.length === 0 ? <MutedNotice text="No variables are available yet. Try indexing a local NWB dataset." /> : null}
      {!loading && variables.length > 0 ? (
        <div className="variable-map">
          {groups.map((group) => (
            <div className="map-column" key={group.name}>
              <div className="map-column-title">{group.name}</div>
              {group.items.slice(0, 24).map((variable) => (
                <button key={variableKey(variable)} onClick={() => onSelect(variable)} className="map-node">
                  <span>{variableName(variable)}</span>
                  <small>{String(variable.neurodata_type ?? variable.kind ?? "variable")}</small>
                </button>
              ))}
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function VariableList({
  variables,
  loading,
  selected,
  onSelect,
  message
}: {
  variables: VariableRecord[];
  loading: boolean;
  selected: VariableRecord | null;
  onSelect: (v: VariableRecord) => void;
  message?: string | null;
}) {
  return (
    <section className="variable-list">
      <div className="section-title compact">
        <h2>Variables</h2>
        <span>{variables.length}</span>
      </div>
      {message ? <p className="muted-small">{message}</p> : null}
      {loading ? (
        Array.from({ length: 8 }).map((_, index) => <VariableSkeleton key={index} />)
      ) : (
        variables.map((variable) => (
          <button
            key={variableKey(variable)}
            onClick={() => onSelect(variable)}
            className={selected && variableKey(selected) === variableKey(variable) ? "variable-row selected" : "variable-row"}
          >
            <span>{variableName(variable)}</span>
            <small>{String(variable.object_path ?? variable.file ?? variable.kind ?? "")}</small>
          </button>
        ))
      )}
    </section>
  );
}

function VariableDetail({
  selected,
  explanation,
  state
}: {
  selected: VariableRecord | null;
  explanation: VariableExplainResponse | null;
  state: LoadState;
}) {
  return (
    <section className="variable-detail">
      {!selected ? (
        <div className="empty-detail">
          <Code2 size={28} />
          <h2>Select a variable</h2>
          <p>Click a variable to get loading code, meaning, provenance notes, and evidence from the local model.</p>
        </div>
      ) : null}
      {selected ? (
        <>
          <h2>{variableName(selected)}</h2>
          {state === "loading" ? <ExplanationLoading /> : null}
          {explanation ? (
            <>
              <div className="code-block">
                <div className="code-title">
                  <Code2 size={16} />
                  <span>Loading Code</span>
                </div>
                <pre>{explanation.loading_code}</pre>
              </div>
              <div className="explanation-copy">
                <Markdown text={explanation.explanation ?? "No explanation was returned."} />
              </div>
              {explanation.ai_error ? <MutedNotice text={explanation.ai_error} /> : null}
            </>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function FlowNode({ icon, label, active }: { icon: React.ReactNode; label: string; active?: boolean }) {
  return (
    <div className={active ? "flow-node active" : "flow-node"}>
      {icon}
      <span>{label}</span>
    </div>
  );
}

function DatasetLoading() {
  return (
    <section className="loading-panel">
      <Loader2 size={26} className="spin" />
      <div>
        <h2>Building the dataset page</h2>
        <p>Fetching DANDI metadata, resolving paper hints, and asking the local model for a grounded overview.</p>
      </div>
    </section>
  );
}

function MapLoading() {
  return (
    <div className="map-loading">
      {Array.from({ length: 16 }).map((_, index) => (
        <span key={index} />
      ))}
    </div>
  );
}

function ExplanationLoading() {
  return (
    <div className="explanation-loading">
      <Loader2 size={22} className="spin" />
      <p>Gathering variable context and asking the local model. This can take a little while.</p>
      <SkeletonLine width="92%" />
      <SkeletonLine width="78%" />
      <SkeletonLine width="84%" />
    </div>
  );
}

function VariableSkeleton() {
  return (
    <div className="variable-skeleton">
      <SkeletonLine width="70%" />
      <SkeletonLine width="44%" />
    </div>
  );
}

function SkeletonLine({ width }: { width: string }) {
  return <span className="skeleton-line" style={{ width }} />;
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <section className="error-panel">
      <TriangleAlert size={22} />
      <p>{message}</p>
    </section>
  );
}

function MutedNotice({ text }: { text: string }) {
  return <p className="muted-notice">{text}</p>;
}

function Fact({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="fact">
      <span>{label}</span>
      <p>{formatValue(value)}</p>
    </div>
  );
}

function Markdown({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/).filter(Boolean);
  return (
    <div className="markdown">
      {blocks.map((block, index) => {
        if (block.startsWith("### ")) return <h3 key={index}>{block.slice(4)}</h3>;
        if (block.startsWith("## ")) return <h3 key={index}>{block.slice(3)}</h3>;
        if (block.startsWith("# ")) return <h3 key={index}>{block.slice(2)}</h3>;
        return <p key={index}>{block.replace(/\*\*/g, "")}</p>;
      })}
    </div>
  );
}

function groupVariables(variables: VariableRecord[]): Array<{ name: string; items: VariableRecord[] }> {
  const map = new globalThis.Map<string, VariableRecord[]>();
  for (const variable of variables) {
    const group = String(variable.modality ?? variable.neurodata_type ?? variable.kind ?? "variables");
    map.set(group, [...(map.get(group) ?? []), variable]);
  }
  return Array.from(map.entries()).map(([name, items]) => ({ name, items }));
}

function variableName(variable: VariableRecord) {
  return String(variable.name ?? variable.variable ?? variable.object_path ?? variable.file ?? "variable");
}

function variableKey(variable: VariableRecord) {
  return JSON.stringify([variable.name, variable.object_path, variable.file, variable.kind]);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "Unknown";
  if (Array.isArray(value)) return value.map((item) => formatValue(item)).join(", ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function numberish(value: unknown) {
  return typeof value === "number" ? value.toLocaleString() : "unknown";
}
