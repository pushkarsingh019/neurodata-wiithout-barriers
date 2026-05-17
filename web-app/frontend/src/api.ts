import type {
  DatasetPage,
  DatasetResolveResponse,
  HealthResponse,
  VariableExplainResponse,
  VariableInventory,
  VariableRecord
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof detail.detail === "string" ? detail.detail : JSON.stringify(detail));
  }
  return (await response.json()) as T;
}

export function getHealth() {
  return request<HealthResponse>("/api/health");
}

export function resolveDataset(value: string) {
  return request<DatasetResolveResponse>("/api/datasets/resolve", {
    method: "POST",
    body: JSON.stringify({ value })
  });
}

export function getDataset(datasetId: string) {
  return request<DatasetPage>(`/api/dandi/${datasetId}`);
}

export function getVariables(datasetId: string) {
  return request<VariableInventory>(`/api/dandi/${datasetId}/variables`);
}

export function explainVariable(datasetId: string, variable: VariableRecord) {
  const name = String(variable.name ?? variable.variable ?? variable.object_path ?? "variable");
  return request<VariableExplainResponse>(`/api/dandi/${datasetId}/variables/explain`, {
    method: "POST",
    body: JSON.stringify({
      variable: name,
      file_path: variable.file ?? variable.file_path ?? null,
      object_path: variable.object_path ?? null
    })
  });
}

export function indexLocal(datasetId: string, path: string) {
  return request(`/api/dandi/${datasetId}/index-local`, {
    method: "POST",
    body: JSON.stringify({ path, dandiset_id: datasetId, inspect_limit: 50 })
  });
}

export function skillUrl(datasetId: string) {
  return `${API_BASE_URL}/api/dandi/${datasetId}/skill.zip`;
}
