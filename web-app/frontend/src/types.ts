export type AiStatus = "ready" | "unavailable" | "error";
export type Provider = "dandi" | "openneuro" | "ibl";

export interface DatasetResolveResponse {
  provider: Provider;
  dataset_id: string;
  route: string;
  source: string;
}

export interface DatasetPage {
  provider: Provider;
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
  provider: Provider;
  dataset_id: string;
  source: "local_index" | "metadata" | "archive";
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
  provider?: Provider;
  dataset_id: string;
  variable: string;
  loading_code: string;
  explanation?: string | null;
  evidence: Array<Record<string, unknown>>;
  context: Record<string, unknown>;
  preview?: VariablePreview | null;
  confidence_label: string;
  ai_status: AiStatus;
  ai_error?: string | null;
}

export interface VariablePreview {
  status?: string;
  shape?: number[] | null;
  rate?: number | string | null;
  unit?: string | null;
  neurodata_type?: string | null;
  sample_axis?: string | null;
  values?: number[];
  intervals?: number[][];
  message?: string | null;
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

export interface SkillStatus {
  provider?: Provider;
  dataset_id: string;
  ready: boolean;
  total_variables: number;
  cached_variables: number;
  missing_variables: Array<Record<string, unknown>>;
  message: string;
  generated_variables?: number;
  failed_variables?: Array<Record<string, unknown>>;
}
