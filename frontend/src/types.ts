// Mirrors backend/app/schemas.py
export interface Name {
  rfc4514: string;
  common_name: string | null;
  organization: string | null;
}

export interface Validity {
  not_before: string;
  not_after: string;
  days_remaining: number;
  expired: boolean;
  not_yet_valid: boolean;
}

export interface Validation {
  trusted: boolean;
  trust_error: string | null;
  trust_error_code: number | null;
  hostname_match: boolean;
  hostname_detail: string;
}

export type CertStatus =
  | "valid"
  | "expiring_soon"
  | "expired"
  | "untrusted"
  | "hostname_mismatch";

export interface InspectResult {
  domain: string;
  ip_address: string;
  tls_version: string;
  cipher: string | null;
  subject: Name;
  issuer: Name;
  validity: Validity;
  sans: string[];
  fingerprint_sha256: string;
  serial_number: string;
  signature_algorithm: string | null;
  public_key: string;
  validation: Validation;
  status: CertStatus;
  warnings: string[];
}

export interface ApiErrorBody {
  code: string;
  message: string;
}

// ---- CertDiff (mirrors backend/app/schemas_diff.py) ----
export type DiffStatus = "UNCHANGED" | "MODIFIED" | "ADDED" | "REMOVED";

export interface CertSummary {
  filename: string;
  subject: string;
  issuer: string;
  serial_number: string;
  not_before: string;
  not_after: string;
  fingerprint_sha256: string;
}

export interface FieldDiff {
  key: string;
  label: string;
  kind: "scalar" | "list";
  status: DiffStatus;
  a: string | string[] | null;
  b: string | string[] | null;
  added: string[];
  removed: string[];
  unchanged: string[];
  explanation: string;
}

export interface DiffResult {
  compared_at: string;
  certificate_a: CertSummary;
  certificate_b: CertSummary;
  summary: Record<DiffStatus, number>;
  fields: FieldDiff[];
}

// ---- Monitor (mirrors backend/app/schemas_monitor.py) ----
export type MonitorStatus =
  | "HEALTHY"
  | "EXPIRING_SOON"
  | "EXPIRED"
  | "INVALID"
  | "CHECK_FAILED"
  | "CHANGED";

export interface FieldChange {
  key: string;
  label: string;
  before: string | null;
  after: string | null;
}

export interface ChangeSet {
  fields: FieldChange[];
  sans_added: string[];
  sans_removed: string[];
  hint: string;
}

export interface Observation {
  id: number;
  observed_at: string;
  outcome: "ok" | "failed";
  status: MonitorStatus;
  ip_address: string | null;
  fingerprint_sha256: string | null;
  issuer: string | null;
  subject: string | null;
  serial_number: string | null;
  not_before: string | null;
  not_after: string | null;
  tls_version: string | null;
  signature_algorithm: string | null;
  public_key: string | null;
  sans: string[];
  trusted: boolean | null;
  trust_error: string | null;
  hostname_match: boolean | null;
  changed: boolean;
  changes: ChangeSet | null;
  error_code: string | null;
  error_message: string | null;
}

export interface MonitoredDomain {
  id: number;
  domain: string;
  added_at: string;
  last_checked_at: string | null;
  last_changed_at: string | null;
  status: MonitorStatus;
  issuer: string | null;
  not_after: string | null;
  days_remaining: number | null;
  fingerprint_sha256: string | null;
  tls_version: string | null;
  last_error: string | null;
}

export interface MonitoredDomainDetail extends MonitoredDomain {
  observations: Observation[];
}
