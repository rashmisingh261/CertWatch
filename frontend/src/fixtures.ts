import type { InspectResult } from "./types";

export const validResult: InspectResult = {
  domain: "example.com",
  ip_address: "93.184.216.34",
  tls_version: "TLSv1.3",
  cipher: "TLS_AES_256_GCM_SHA384",
  subject: { rfc4514: "CN=example.com", common_name: "example.com", organization: "Example Inc" },
  issuer: { rfc4514: "CN=Test CA", common_name: "Test CA", organization: "Test CA Org" },
  validity: {
    not_before: "2026-01-01T00:00:00+00:00",
    not_after: "2026-12-31T00:00:00+00:00",
    days_remaining: 42,
    expired: false,
    not_yet_valid: false,
  },
  sans: ["example.com", "www.example.com"],
  fingerprint_sha256: "AA:BB:CC",
  serial_number: "1A2B",
  signature_algorithm: "sha256",
  public_key: "EC secp256r1",
  validation: {
    trusted: true,
    trust_error: null,
    trust_error_code: null,
    hostname_match: true,
    hostname_detail: "'example.com' matches the certificate's Subject Alternative Names.",
  },
  status: "valid",
  warnings: [],
};
