import {
  Activity,
  ArrowRight,
  BookOpen,
  BrainCircuit,
  Check,
  Code2,
  Clipboard,
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
  getSkillStatus,
  getVariables,
  indexLocal,
  resolveDataset,
  skillUrl
} from "./api";
import type { DatasetPage, Provider, SkillStatus, VariableExplainResponse, VariableInventory, VariablePreview, VariableRecord } from "./types";

type LoadState = "idle" | "loading" | "ready" | "error";
type DatasetRoute = { provider: Provider; datasetId: string };

function routeDataset(): DatasetRoute | null {
  const match = window.location.pathname.match(/^\/data\/(dandi|openneuro|ibl)_(.+)$/);
  if (!match) return null;
  return { provider: match[1] as Provider, datasetId: decodeURIComponent(match[2]) };
}

function routeIsDocs(): boolean {
  return window.location.pathname === "/docs";
}

export function App() {
  const [datasetRoute, setDatasetRoute] = useState<DatasetRoute | null>(() => routeDataset());
  const [docsOpen, setDocsOpen] = useState(() => routeIsDocs());

  const navigate = (provider: Provider, id: string) => {
    window.history.pushState({}, "", `/data/${provider}_${encodeURIComponent(id)}`);
    setDocsOpen(false);
    setDatasetRoute({ provider, datasetId: id });
  };

  const openDocs = () => {
    window.history.pushState({}, "", "/docs");
    setDatasetRoute(null);
    setDocsOpen(true);
  };

  useEffect(() => {
    const onPop = () => {
      setDatasetRoute(routeDataset());
      setDocsOpen(routeIsDocs());
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  return (
    <div className="app-shell">
      <TopBar onHome={() => navigateHome(setDatasetRoute, setDocsOpen)} onDocs={openDocs} />
      {datasetRoute ? <DatasetView provider={datasetRoute.provider} datasetId={datasetRoute.datasetId} /> : docsOpen ? <Documentation /> : <Landing onNavigate={navigate} />}
    </div>
  );
}

function navigateHome(setDatasetRoute: (value: DatasetRoute | null) => void, setDocsOpen: (value: boolean) => void) {
  window.history.pushState({}, "", "/");
  setDatasetRoute(null);
  setDocsOpen(false);
}

function TopBar({ onHome, onDocs }: { onHome: () => void; onDocs: () => void }) {
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
      </div>
    </header>
  );
}

function Landing({ onNavigate }: { onNavigate: (provider: Provider, datasetId: string) => void }) {
  const [value, setValue] = useState("");
  const [state, setState] = useState<LoadState>("idle");
  const [error, setError] = useState<string | null>(null);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setState("loading");
    setError(null);
    try {
      const result = await resolveDataset(value);
      onNavigate(result.provider, result.dataset_id);
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
          <span>DANDI, OpenNeuro, and IBL explorer with cached dataset context</span>
        </div>
        <h1>Neurodata Without Barriers</h1>
        <p className="tagline">Where centuries of research data come alive.</p>
        <form className="resolver" onSubmit={submit}>
          <Search size={20} />
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="Paste DANDI, OpenNeuro, or IBL, e.g. 001097, ds000001, or an OpenAlyx UUID"
            aria-label="Dataset URL or ID"
          />
          <button type="submit" disabled={state === "loading"}>
            {state === "loading" ? <Loader2 size={18} className="spin" /> : <ArrowRight size={18} />}
            <span>Explore</span>
          </button>
        </form>
        {error ? <p className="inline-error">{error}</p> : null}
        <div className="quick-row">
          <button onClick={() => onNavigate("dandi", "001097")}>
            <Database size={17} />
            <span>Open DANDI example 001097</span>
          </button>
          <button onClick={() => onNavigate("openneuro", "ds000001")}>
            <Globe2 size={17} />
            <span>Open OpenNeuro ds000001</span>
          </button>
          <div className="quiet-note">Cached demo ready</div>
        </div>
      </section>
      <section className="landing-visual" aria-label="Dataset flow preview">
        <div className="flow-row">
          <FlowNode icon={<Database size={19} />} label="Archive metadata" active />
          <FlowNode icon={<Activity size={19} />} label="Variables" active />
          <FlowNode icon={<Sparkles size={19} />} label="Cached context" active />
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

function DatasetView({ provider, datasetId }: { provider: Provider; datasetId: string }) {
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
  const [skillStatus, setSkillStatus] = useState<SkillStatus | null>(null);
  const [skillState, setSkillState] = useState<LoadState>("loading");
  const [skillPrepOpen, setSkillPrepOpen] = useState(false);
  const [skillPrepRunning, setSkillPrepRunning] = useState(false);
  const [skillPrepItems, setSkillPrepItems] = useState<Array<{ label: string; state: LoadState }>>([]);
  const [skillPrepMessage, setSkillPrepMessage] = useState<string | null>(null);

  useEffect(() => {
    setDataset(null);
    setVariables(null);
    setSelected(null);
    setExplanation(null);
    setDatasetState("loading");
    setVariableState("loading");
    setSkillStatus(null);
    setSkillState("loading");
    setError(null);
    getDataset(provider, datasetId)
      .then((data) => {
        setDataset(data);
        setDatasetState("ready");
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Dataset failed to load.");
        setDatasetState("error");
      });
    getVariables(provider, datasetId)
      .then((data) => {
        setVariables(data);
        setVariableState("ready");
      })
      .catch(() => setVariableState("error"));
    refreshSkillStatus();
  }, [provider, datasetId]);

  const refreshSkillStatus = async () => {
    setSkillState("loading");
    try {
      const status = await getSkillStatus(provider, datasetId);
      setSkillStatus(status);
      setSkillState("ready");
      return status;
    } catch {
      setSkillState("error");
      return null;
    }
  };

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
      const result = await explainVariable(provider, datasetId, variable);
      setExplanation(result);
      setExplainState("ready");
    } catch (err) {
      setExplanation({
        dataset_id: datasetId,
        provider,
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
      const result = await indexLocal(provider, datasetId, localPath);
      setIndexMessage(String((result as { message?: string }).message ?? `Index status: ${(result as { status?: string }).status}`));
      const next = await getVariables(provider, datasetId);
      setVariables(next);
      await refreshSkillStatus();
    } catch (err) {
      setIndexMessage(err instanceof Error ? err.message : "Local indexing failed.");
    } finally {
      setIndexing(false);
    }
  };

  const downloadSkill = () => {
    window.location.href = skillUrl(provider, datasetId);
  };

  const prepareAndDownloadSkill = async () => {
    setSkillPrepOpen(true);
    setSkillPrepRunning(true);
    setSkillPrepMessage("Checking cached variable explanations.");
    const status = skillStatus?.ready ? skillStatus : await refreshSkillStatus();
    if (status?.ready) {
      setSkillPrepRunning(false);
      setSkillPrepMessage("All variable explanations are cached. Downloading skill.");
      downloadSkill();
      return;
    }

    const missing = (status?.missing_variables ?? []) as VariableRecord[];
    if (!missing.length) {
      setSkillPrepRunning(false);
      setSkillPrepMessage("No variables are available yet. Index the local dataset first.");
      return;
    }

    setSkillPrepItems(missing.map((item) => ({ label: variableLabel(item), state: "idle" })));
    setSkillPrepMessage(`Generating explanations for ${missing.length} variables before export.`);

    for (let index = 0; index < missing.length; index += 1) {
      const variable = missing[index];
      setSkillPrepItems((items) => items.map((item, i) => (i === index ? { ...item, state: "loading" } : item)));
      try {
        await explainVariable(provider, datasetId, variable);
        setSkillPrepItems((items) => items.map((item, i) => (i === index ? { ...item, state: "ready" } : item)));
      } catch {
        setSkillPrepItems((items) => items.map((item, i) => (i === index ? { ...item, state: "error" } : item)));
      }
    }

    const finalStatus = await refreshSkillStatus();
    setSkillPrepRunning(false);
    if (finalStatus?.ready) {
      setSkillPrepMessage("All variables are ready. Downloading the standalone skill.");
      downloadSkill();
    } else {
      setSkillPrepMessage(finalStatus?.message ?? "Skill preparation finished, but some variables still need context.");
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
              provider={provider}
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
          <button className="icon-action" onClick={prepareAndDownloadSkill} title={skillStatus?.message ?? "Prepare and download dataset skill"}>
            <Download size={18} />
            <span>{skillState === "loading" ? "Checking" : skillStatus?.ready ? "Skill" : `${skillStatus?.cached_variables ?? 0}/${skillStatus?.total_variables ?? 0}`}</span>
          </button>
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
      {skillPrepOpen ? (
        <SkillPrepModal
          items={skillPrepItems}
          message={skillPrepMessage}
          running={skillPrepRunning}
          onClose={() => setSkillPrepOpen(false)}
          onDownload={skillStatus?.ready ? downloadSkill : undefined}
        />
      ) : null}
    </main>
  );
}

function DatasetHeader({ dataset }: { dataset: DatasetPage }) {
  const title = String(dataset.summary.name ?? dataset.summary.Name ?? `${providerLabel(dataset.provider)} ${dataset.dataset_id}`);
  const url = datasetUrl(dataset.provider, dataset.dataset_id, dataset.summary);
  return (
    <section className="dataset-header">
      <div>
        <p className="dataset-kicker">{providerLabel(dataset.provider)} {dataset.dataset_id}</p>
        <h1>{title}</h1>
        <div className="fact-row">
          <span><Database size={15} /> {numberish(dataset.assets.count)} records</span>
          <span><FileText size={15} /> {dataset.papers.length} paper links</span>
          <span><BrainCircuit size={15} /> {dataset.ai_status === "ready" ? "AI overview ready" : "AI unavailable"}</span>
        </div>
      </div>
      <a className="primary-link" href={url} target="_blank" rel="noreferrer">
        <ArrowRight size={18} />
        <span>{providerLabel(dataset.provider)}</span>
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
        <Fact label="Provider" value={providerLabel(dataset.provider)} />
        <Fact label="License" value={dataset.summary.license ?? dataset.summary.License} />
        <Fact label="Version" value={dataset.version} />
        <Fact label="Citation" value={dataset.summary.citation ?? dataset.summary.doi ?? dataset.summary.DatasetDOI} />
        <Fact label="Keywords" value={dataset.summary.keywords ?? dataset.summary.modalities ?? dataset.summary.tasks} />
      </div>
    </section>
  );
}

function LocalIndexPanel({
  provider,
  localPath,
  setLocalPath,
  indexing,
  indexMessage,
  onIndex
}: {
  provider: Provider;
  localPath: string;
  setLocalPath: (value: string) => void;
  indexing: boolean;
  indexMessage: string | null;
  onIndex: () => void;
}) {
  const label = provider === "dandi" ? "Local NWB Index" : provider === "openneuro" ? "Local BIDS Index" : "Local ALF Index";
  const description =
    provider === "dandi"
      ? "Paste a local Dandiset path to unlock object paths, shapes, rates, units, and richer variable explanations."
      : provider === "openneuro"
        ? "Paste a local OpenNeuro/BIDS dataset path to unlock event tables, subjects, tasks, modalities, and richer previews."
        : "Paste a local IBL/ALF session path to unlock local arrays, collections, ALF objects, and richer previews.";
  const placeholder = provider === "dandi" ? "/absolute/path/to/dandiset" : provider === "openneuro" ? "/absolute/path/to/BIDS-dataset" : "/absolute/path/to/IBL-session";
  return (
    <section className="index-panel">
      <div>
        <h2>{label}</h2>
        <p>{description}</p>
      </div>
      <div className="index-controls">
        <input value={localPath} onChange={(event) => setLocalPath(event.target.value)} placeholder={placeholder} />
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
              <VariablePreviewPanel selected={selected} explanation={explanation} />
              <CodeBlock code={explanation.loading_code} lang="python" />
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

function VariablePreviewPanel({
  selected,
  explanation
}: {
  selected: VariableRecord;
  explanation: VariableExplainResponse;
}) {
  const preview = normalizedPreview(selected, explanation);
  const hasValues = Boolean(preview.values?.length);
  return (
    <section className="variable-preview-card">
      <div className="variable-preview-header">
        <div>
          <p className="dataset-kicker">Variable Preview</p>
          <h3>{hasValues ? "Sampled signal" : "Shape view"}</h3>
        </div>
        <span className={`preview-status ${preview.status ?? "metadata_only"}`}>{preview.status ?? "metadata only"}</span>
      </div>
      <div className="preview-facts">
        <PreviewFact label="Shape" value={formatShape(preview.shape)} />
        <PreviewFact label="Type" value={preview.neurodata_type ?? String(selected.neurodata_type ?? selected.kind ?? "variable")} />
        <PreviewFact label="Rate" value={formatNullable(preview.rate ?? selected.rate)} />
        <PreviewFact label="Unit" value={formatNullable(preview.unit ?? selected.unit ?? selected.units)} />
      </div>
      <VariablePlot preview={preview} />
      {preview.sample_axis ? <p className="preview-note">Preview axis: {preview.sample_axis}</p> : null}
      {preview.message && !hasValues ? <p className="preview-note">{preview.message}</p> : null}
    </section>
  );
}

function PreviewFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="preview-fact">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function VariablePlot({ preview }: { preview: VariablePreview }) {
  const values = preview.values?.filter((value) => Number.isFinite(value)) ?? [];
  if (values.length >= 2) {
    return <LinePlot values={values} />;
  }
  return <ShapePlot shape={preview.shape ?? []} />;
}

function LinePlot({ values }: { values: number[] }) {
  const width = 340;
  const height = 128;
  const padding = 14;
  const finiteValues = values.filter((value) => Number.isFinite(value)).slice(0, 240);
  const min = Math.min(...finiteValues);
  const max = Math.max(...finiteValues);
  const spread = max - min || 1;
  const points = finiteValues
    .map((value, index) => {
      const x = padding + (index / Math.max(finiteValues.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((value - min) / spread) * (height - padding * 2);
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  return (
    <div className="plot-shell">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Sampled variable line plot">
        <line x1={padding} y1={height - padding} x2={width - padding} y2={height - padding} />
        <line x1={padding} y1={padding} x2={padding} y2={height - padding} />
        <polyline points={points} />
      </svg>
      <div className="plot-scale">
        <span>{formatNumber(min)}</span>
        <span>{finiteValues.length} sampled points</span>
        <span>{formatNumber(max)}</span>
      </div>
    </div>
  );
}

function ShapePlot({ shape }: { shape: number[] }) {
  const dims = shape.length ? shape : [1];
  const max = Math.max(...dims.map((item) => Math.max(item, 1)));
  return (
    <div className="shape-plot" aria-label="Variable shape visualization">
      {dims.map((dim, index) => (
        <div className="shape-dimension" key={`${dim}-${index}`}>
          <span style={{ width: `${Math.max(14, (Math.max(dim, 1) / max) * 100)}%` }} />
          <strong>dim {index + 1}</strong>
          <small>{formatNumber(dim)}</small>
        </div>
      ))}
    </div>
  );
}

function SkillPrepModal({
  items,
  message,
  running,
  onClose,
  onDownload
}: {
  items: Array<{ label: string; state: LoadState }>;
  message: string | null;
  running: boolean;
  onClose: () => void;
  onDownload?: () => void;
}) {
  const readyCount = items.filter((item) => item.state === "ready").length;
  const total = items.length;
  const progress = total ? Math.round((readyCount / total) * 100) : 100;
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <section className="skill-modal">
        <div className="skill-modal-header">
          <div>
            <p className="dataset-kicker">Skill Export</p>
            <h2>Preparing standalone dataset context</h2>
          </div>
          <button className="modal-close" onClick={onClose} disabled={running}>
            Close
          </button>
        </div>
        <p className="muted-notice">
          {message ?? "Before downloading, the app explains every variable and stores the metadata, evidence, and loading code in the skill."}
        </p>
        <div className="skill-progress">
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="skill-progress-label">
          <span>{readyCount}/{total || 0} variables ready</span>
          {running ? <Loader2 size={16} className="spin" /> : null}
        </div>
        <div className="skill-variable-list">
          {items.length ? (
            items.map((item, index) => (
              <div className={`skill-variable ${item.state}`} key={`${item.label}-${index}`}>
                {item.state === "loading" ? <Loader2 size={15} className="spin" /> : item.state === "ready" ? <Database size={15} /> : item.state === "error" ? <TriangleAlert size={15} /> : <FileText size={15} />}
                <span>{item.label}</span>
              </div>
            ))
          ) : (
            <div className="skill-empty-state">
              <Loader2 size={18} className={running ? "spin" : ""} />
              <span>{running ? "Checking skill readiness" : "No missing variables"}</span>
            </div>
          )}
        </div>
        <div className="skill-modal-actions">
          <button className="secondary-button" onClick={onClose} disabled={running}>
            Keep Browsing
          </button>
          {onDownload ? (
            <button className="primary-button" onClick={onDownload}>
              <Download size={17} />
              <span>Download Skill</span>
            </button>
          ) : null}
        </div>
      </section>
    </div>
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

type MarkdownBlock =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "code"; code: string; lang: string }
  | { type: "ul" | "ol"; items: string[] };

const SECTION_LABELS = [
  "Dataset Overview",
  "What this dataset is",
  "What is inside",
  "Why it may matter",
  "Good next steps",
  "Meaning",
  "How to load it",
  "How it was likely generated or recorded",
  "What to watch out for",
  "Evidence"
];

const SECTION_LABEL_PATTERN = SECTION_LABELS.map(escapeRegExp).join("|");

function Markdown({ text }: { text: string }) {
  const blocks = parseMarkdown(text);
  return (
    <div className="markdown">
      {blocks.map((block, index) => {
        if (block.type === "heading") return <h3 key={index}>{renderInline(block.text)}</h3>;
        if (block.type === "paragraph") return <p key={index}>{renderInline(block.text)}</p>;
        if (block.type === "code") {
          return <CodeBlock key={index} code={block.code} lang={block.lang} />;
        }
        if (block.type === "ul") {
          return (
            <ul key={index}>
              {block.items.map((line, itemIndex) => (
                <li key={itemIndex}>{renderInline(line)}</li>
              ))}
            </ul>
          );
        }
        return (
          <ol key={index}>
            {block.items.map((line, itemIndex) => (
              <li key={itemIndex}>{renderInline(line)}</li>
            ))}
          </ol>
        );
      })}
    </div>
  );
}

function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false);
  const label = normalizeCodeLanguage(lang, code);

  const copyCode = async () => {
    try {
      await copyText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1400);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="code-block-shell">
      <div className="code-block-toolbar">
        <span>{label}</span>
        <button type="button" className="code-copy-button" onClick={copyCode} aria-label="Copy code block">
          {copied ? <Check size={14} /> : <Clipboard size={14} />}
          <span>{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <pre className={`markdown-code language-${label}`}>
        <code>{renderCode(code, label)}</code>
      </pre>
    </div>
  );
}

function parseMarkdown(text: string): MarkdownBlock[] {
  const normalized = normalizeMarkdown(text);
  const lines = normalized.split("\n");
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let inCode = false;
  let codeLang = "";
  let codeLines: string[] = [];

  const flushParagraph = () => {
    const value = cleanupMarkdownText(paragraph.join(" "));
    paragraph = [];
    if (!value) return;
    blocks.push(...splitSectionParagraph(value));
  };

  const flushList = () => {
    if (listType && listItems.length) {
      blocks.push({ type: listType, items: listItems.map(cleanupMarkdownText).filter(Boolean) });
    }
    listItems = [];
    listType = null;
  };

  for (const rawLine of lines) {
    const fenceMatch = rawLine.match(/^```\s*([\w-]*)\s*$/);
    if (fenceMatch) {
      if (inCode) {
        blocks.push({ type: "code", code: codeLines.join("\n").trimEnd(), lang: codeLang });
        inCode = false;
        codeLang = "";
        codeLines = [];
      } else {
        flushParagraph();
        flushList();
        inCode = true;
        codeLang = fenceMatch[1] ?? "";
        codeLines = [];
      }
      continue;
    }

    if (inCode) {
      codeLines.push(rawLine);
      continue;
    }

    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      flushList();
      continue;
    }

    const heading = line.match(/^#{1,6}\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", text: cleanupMarkdownText(heading[1]) });
      continue;
    }

    const unordered = line.match(/^[-*]\s+(.+)$/);
    if (unordered) {
      flushParagraph();
      if (listType !== "ul") flushList();
      listType = "ul";
      listItems.push(unordered[1]);
      continue;
    }

    const ordered = line.match(/^\d+\.\s+(.+)$/);
    if (ordered) {
      flushParagraph();
      if (listType !== "ol") flushList();
      listType = "ol";
      listItems.push(ordered[1]);
      continue;
    }

    flushList();
    paragraph.push(line);
  }

  if (inCode) {
    blocks.push({ type: "code", code: codeLines.join("\n").trimEnd(), lang: codeLang });
  }
  flushParagraph();
  flushList();
  return blocks;
}

function splitSectionParagraph(text: string): MarkdownBlock[] {
  const exactSection = SECTION_LABELS.find((label) => label.toLowerCase() === text.toLowerCase());
  if (exactSection) return [{ type: "heading", text: exactSection }];

  const escaped = SECTION_LABEL_PATTERN;
  const boldSection = text.match(new RegExp(`^\\*\\*(${escaped})\\*\\*[:.]?\\s*(.*)$`, "i"));
  const plainSection = text.match(new RegExp(`^(${escaped})(?::|\\s+)(.*)$`, "i"));
  const match = boldSection ?? plainSection;
  if (!match) return [{ type: "paragraph", text }];

  const heading = canonicalSectionLabel(match[1]);
  const rest = cleanupMarkdownText(match[2] ?? "");
  return rest ? [{ type: "heading", text: heading }, { type: "paragraph", text: rest }] : [{ type: "heading", text: heading }];
}

function normalizeMarkdown(text: string): string {
  let normalized = text.replace(/\r\n/g, "\n").trim();
  normalized = normalized.replace(/```([A-Za-z0-9_-]+)[ \t]+/g, "\n```$1\n");
  normalized = normalized.replace(/([^\n])```/g, "$1\n```");
  normalized = normalized.replace(/```[ \t]+(?=[A-Z])/g, "```\n");
  normalized = normalized.replace(new RegExp(`\\*\\*(${SECTION_LABEL_PATTERN})\\*\\*[:.]?\\s*`, "gi"), "\n\n### $1\n\n");
  normalized = normalized.replace(/([^\n])\s+(-\s+\*\*)/g, "$1\n$2");
  normalized = normalized.replace(/\s+\*\s+(?=\*\*?[A-Z])/g, "\n- ");
  normalized = normalized.replace(/\s+\*\s+\*\*/g, "\n- **");
  normalized = normalized.replace(/\n{3,}/g, "\n\n");
  return normalized;
}

function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const cleaned = cleanupMarkdownText(text);
  const pattern = /(`[^`]+`|\*\*.+?\*\*)/g;
  let cursor = 0;
  let match: RegExpExecArray | null;
  while ((match = pattern.exec(cleaned))) {
    if (match.index > cursor) {
      nodes.push(cleaned.slice(cursor, match.index));
    }
    const token = match[0];
    if (token.startsWith("**")) {
      nodes.push(<strong key={`${match.index}-strong`}>{cleanupMarkdownText(token.slice(2, -2))}</strong>);
    } else if (token.startsWith("`")) {
      nodes.push(<code key={`${match.index}-code`}>{token.slice(1, -1)}</code>);
    }
    cursor = match.index + token.length;
  }
  if (cursor < cleaned.length) {
    nodes.push(cleaned.slice(cursor));
  }
  return nodes;
}

function renderCode(code: string, lang: string): React.ReactNode[] | string {
  const isPython = /python|py/i.test(lang) || /\b(from|import|with)\s+\w+/.test(code);
  if (!isPython) return code;

  const nodes: React.ReactNode[] = [];
  const tokenPattern =
    /(#.*$|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:and|as|assert|break|class|continue|def|del|elif|else|except|False|finally|for|from|if|import|in|is|lambda|None|not|or|pass|raise|return|True|try|while|with|yield)\b|\b(?:NWBHDF5IO|Path|print|len|range|open|list|dict|set|tuple|str|int|float|bool)\b|\b\d+(?:\.\d+)?\b)/g;

  code.split("\n").forEach((line, lineIndex, lines) => {
    let cursor = 0;
    let match: RegExpExecArray | null;
    while ((match = tokenPattern.exec(line))) {
      if (match.index > cursor) nodes.push(line.slice(cursor, match.index));
      const token = match[0];
      nodes.push(
        <span className={`code-token ${codeTokenClass(token)}`} key={`${lineIndex}-${match.index}`}>
          {token}
        </span>
      );
      cursor = match.index + token.length;
    }
    if (cursor < line.length) nodes.push(line.slice(cursor));
    if (lineIndex < lines.length - 1) nodes.push("\n");
  });

  return nodes;
}

function normalizeCodeLanguage(lang: string, code: string): string {
  const normalized = lang.trim().toLowerCase();
  if (normalized) return normalized === "py" ? "python" : normalized;
  if (/\b(from|import|with)\s+\w+/.test(code)) return "python";
  if (/[{;]\s*$/.test(code)) return "code";
  return "code";
}

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  document.body.removeChild(textarea);
}

function codeTokenClass(token: string): string {
  if (token.startsWith("#")) return "comment";
  if (token.startsWith("\"") || token.startsWith("'")) return "string";
  if (/^\d/.test(token)) return "number";
  if (/^(NWBHDF5IO|Path|print|len|range|open|list|dict|set|tuple|str|int|float|bool)$/.test(token)) return "builtin";
  return "keyword";
}

function cleanupMarkdownText(text: string): string {
  return text
    .replace(/(^|\s)\*(?=\S)(?!\*)/g, "$1")
    .replace(/(?<!\*)\*(?=\s|$)/g, "")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function canonicalSectionLabel(text: string): string {
  const normalized = text.toLowerCase();
  return SECTION_LABELS.find((label) => label.toLowerCase() === normalized) ?? text;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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

function variableLabel(variable: VariableRecord) {
  const name = variableName(variable);
  const file = String(variable.file ?? variable.file_path ?? "");
  return file ? `${name} · ${file}` : name;
}

function normalizedPreview(selected: VariableRecord, explanation: VariableExplainResponse): VariablePreview {
  const context = explanation.context ?? {};
  const unit = explanation.preview?.unit ?? String(context.unit ?? context.units ?? selected.unit ?? selected.units ?? "");
  const neurodataType = explanation.preview?.neurodata_type ?? String(context.neurodata_type ?? selected.neurodata_type ?? selected.kind ?? "");
  return {
    status: explanation.preview?.status ?? (explanation.preview?.values?.length ? "sampled" : "metadata_only"),
    shape: explanation.preview?.shape ?? asShape(context.shape ?? selected.shape),
    rate: explanation.preview?.rate ?? (context.rate as string | number | null | undefined) ?? selected.rate,
    unit: unit || null,
    neurodata_type: neurodataType || null,
    sample_axis: explanation.preview?.sample_axis ?? null,
    values: explanation.preview?.values ?? [],
    intervals: explanation.preview?.intervals ?? [],
    message: explanation.preview?.message ?? null
  };
}

function asShape(value: unknown): number[] | null {
  if (Array.isArray(value)) {
    const shape = value.map((item) => Number(item)).filter((item) => Number.isFinite(item));
    return shape.length ? shape : null;
  }
  if (typeof value === "number" && Number.isFinite(value)) return [value];
  return null;
}

function formatShape(shape?: number[] | null): string {
  return shape?.length ? shape.map(formatNumber).join(" x ") : "unknown";
}

function formatNullable(value: unknown): string {
  if (value === null || value === undefined || value === "") return "unknown";
  if (typeof value === "number") return formatNumber(value);
  return String(value);
}

function formatNumber(value: number): string {
  if (!Number.isFinite(value)) return "unknown";
  if (Math.abs(value) >= 10000) return value.toExponential(2);
  if (Math.abs(value) > 0 && Math.abs(value) < 0.01) return value.toExponential(2);
  if (Number.isInteger(value)) return value.toLocaleString();
  return value.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

function providerLabel(provider: Provider): string {
  if (provider === "openneuro") return "OpenNeuro";
  if (provider === "ibl") return "IBL";
  return "DANDI";
}

function datasetUrl(provider: Provider, datasetId: string, summary: Record<string, unknown>): string {
  if (typeof summary.url === "string") return summary.url;
  if (provider === "openneuro") return `https://openneuro.org/datasets/${datasetId}`;
  if (provider === "ibl") return `https://openalyx.internationalbrainlab.org/admin/actions/session/${datasetId}`;
  return `https://dandiarchive.org/dandiset/${datasetId}`;
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
