import type {
  DiffResult,
  InspectResult,
  MonitoredDomain,
  MonitoredDomainDetail,
} from "../types";

export class ApiError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}

/** Shared request helper: network errors and `{error: {code, message}}` bodies become ApiError. */
async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("network", "Could not reach the CertWatch server. Is the backend running?");
  }
  if (res.status === 204) return undefined as T;
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* non-JSON body */
  }
  if (!res.ok) {
    const e = (data as { error?: { code?: string; message?: string } } | null)?.error;
    throw new ApiError(e?.code ?? "http_error", e?.message ?? `Request failed (HTTP ${res.status}).`);
  }
  return data as T;
}

const jsonPost = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

// ---- Inspector ----
export const inspectDomain = (domain: string, signal?: AbortSignal) =>
  apiFetch<InspectResult>("/api/inspect", { ...jsonPost({ domain }), signal });

// ---- CertDiff ----
export function compareCertificates(fileA: File, fileB: File, signal?: AbortSignal) {
  const form = new FormData();
  form.append("certificate_a", fileA);
  form.append("certificate_b", fileB);
  return apiFetch<DiffResult>("/api/certdiff", { method: "POST", body: form, signal });
}

// ---- Monitor ----
export const listMonitored = () => apiFetch<MonitoredDomain[]>("/api/monitor");

export const getMonitored = (id: number) => apiFetch<MonitoredDomainDetail>(`/api/monitor/${id}`);

export const addMonitored = (domain: string) =>
  apiFetch<MonitoredDomainDetail>("/api/monitor", jsonPost({ domain }));

export const checkMonitored = (id: number) =>
  apiFetch<MonitoredDomainDetail>(`/api/monitor/${id}/check`, { method: "POST" });

export const removeMonitored = (id: number) =>
  apiFetch<void>(`/api/monitor/${id}`, { method: "DELETE" });
