export type AiStatus = "ready" | "unavailable" | "error";

export interface DatasetResolveResponse {
  provider: "dandi";
  dataset_id: string;
  route: string;
  source: string;
}

export interface DatasetPage {
  provider: "dandi";
  dataset_id: string;
  version: string;
  route: string;
  summary: Record<string, unknown>;
  neuroscience: Record<string, unknown>;
  papers: Array<Record<string, unknown>>;
  assets: {
    count?: number;
    sample?: Array<Record<string, unknown>>;
    next?: string | null;
  };
  ai_overview?: string | null;
  ai_status: AiStatus;
  ai_error?: string | null;
}

export interface VariableInventory {
  dataset_id: string;
  source: "local_index" | "metadata";
  local_index_status: "indexed" | "not_indexed" | "missing_dependency" | "error";
  variables: VariableRecord[];
  message?: string | null;
}

export interface VariableRecord {
  provider?: string;
  name?: string;
  variable?: string;
  kind?: string;
  file?: string;
  file_path?: string;
  object_path?: string;
  neurodata_type?: string;
  shape?: unknown;
  rate?: number | null;
  unit?: string | null;
  units?: string | null;
  confidence_label?: string;
  modality?: string;
  size_bytes?: number | null;
  [key: string]: unknown;
}

export interface VariableExplainResponse {
  dataset_id: string;
  variable: string;
  loading_code: string;
  explanation?: string | null;
  evidence: Array<Record<string, unknown>>;
  context: Record<string, unknown>;
  confidence_label: string;
  ai_status: AiStatus;
  ai_error?: string | null;
}

export interface HealthResponse {
  status: string;
  llm: {
    status: "ready" | "unavailable";
    base_url: string;
    model?: string;
    error?: string;
  };
  storage_dir: string;
}

