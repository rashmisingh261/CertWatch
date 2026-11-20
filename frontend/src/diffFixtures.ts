import type { DiffResult } from "./types";

const scalar = (key: string, label: string, status: DiffResult["fields"][0]["status"], a: string | null, b: string | null, explanation = "expl") =>
  ({ key, label, kind: "scalar" as const, status, a, b, added: [], removed: [], unchanged: [], explanation });

export const diffResult: DiffResult = {
  compared_at: "2026-02-03T04:05:06+00:00",
  certificate_a: { filename: "a.pem", subject: "CN=example.com", issuer: "CN=CA One", serial_number: "1", not_before: "2026-01-01T00:00:00+00:00", not_after: "2026-04-01T00:00:00+00:00", fingerprint_sha256: "AA" },
  certificate_b: { filename: "b.pem", subject: "CN=example.com", issuer: "CN=CA Two", serial_number: "2", not_before: "2026-02-01T00:00:00+00:00", not_after: "2026-05-01T00:00:00+00:00", fingerprint_sha256: "BB" },
  summary: { UNCHANGED: 2, MODIFIED: 2, ADDED: 1, REMOVED: 0 },
  fields: [
    scalar("subject", "Subject", "UNCHANGED", "CN=example.com", "CN=example.com"),
    scalar("issuer", "Issuer", "MODIFIED", "CN=CA One", "CN=CA Two", "Different CAs."),
    {
      key: "sans", label: "Subject Alternative Names", kind: "list", status: "MODIFIED",
      a: ["DNS:example.com", "DNS:www.example.com"], b: ["DNS:api.example.com", "DNS:example.com"],
      added: ["DNS:api.example.com"], removed: ["DNS:www.example.com"], unchanged: ["DNS:example.com"],
      explanation: "1 added in B, 1 removed from A.",
    },
    scalar("basic_constraints", "Basic Constraints", "ADDED", null, "CA: false"),
    {
      key: "key_usage", label: "Key Usage", kind: "list", status: "UNCHANGED",
      a: [], b: [], added: [], removed: [], unchanged: [], explanation: "not present",
    },
  ],
};
