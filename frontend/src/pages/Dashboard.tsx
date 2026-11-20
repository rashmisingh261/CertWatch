import { useRef, useState } from "react";
import { ApiError, inspectDomain } from "../api/client";
import { CertDetails } from "../components/CertDetails";
import { DomainForm } from "../components/DomainForm";
import { ErrorAlert } from "../components/ErrorAlert";
import { ExpiryCard } from "../components/ExpiryCard";
import { StatusBanner } from "../components/StatusBanner";
import type { InspectResult } from "../types";

export function Dashboard() {
  const [result, setResult] = useState<InspectResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  async function run(domain: string) {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await inspectDomain(domain, ctrl.signal));
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      if (abortRef.current === ctrl) setLoading(false);
    }
  }

  return (
    <div>
      <header>
        <h1>🔒 CertWatch</h1>
        <p className="muted">Inspect the TLS certificate served by any public domain on port 443.</p>
      </header>

      <DomainForm loading={loading} onSubmit={run} />

      {error && <ErrorAlert message={error} />}
      {loading && <p className="muted" aria-live="polite">Connecting and reading certificate…</p>}

      {result && (
        <div className="results">
          <StatusBanner result={result} />
          <ExpiryCard validity={result.validity} />
          <CertDetails result={result} />
        </div>
      )}

      <footer className="muted">
        CertWatch only connects to public hosts on port 443. Private and internal addresses are blocked.
      </footer>
    </div>
  );
}
