import { useRef, useState } from "react";
import { ApiError, compareCertificates } from "../api/client";
import { DiffTable } from "../components/DiffTable";
import { ErrorAlert } from "../components/ErrorAlert";
import { FileDropzone } from "../components/FileDropzone";
import { downloadReport } from "../lib/exportReport";
import type { DiffResult } from "../types";

export function CertDiffPage() {
  const [fileA, setFileA] = useState<File | null>(null);
  const [fileB, setFileB] = useState<File | null>(null);
  const [result, setResult] = useState<DiffResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  async function compare() {
    if (!fileA || !fileB) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await compareCertificates(fileA, fileB, ctrl.signal));
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
    } finally {
      if (abortRef.current === ctrl) setLoading(false);
    }
  }

  function reject(message: string) {
    setError(message);
  }

  return (
    <>
      <header>
        <h1>🔍 CertDiff</h1>
        <p className="muted">
          Upload two PEM certificates to see what changed between them. Files are analysed in memory
          and never stored. Never upload private keys.
        </p>
      </header>

      <div className="grid uploads">
        <FileDropzone label="Certificate A" file={fileA} disabled={loading} onChange={(f) => { setFileA(f); setError(null); }} onReject={reject} />
        <FileDropzone label="Certificate B" file={fileB} disabled={loading} onChange={(f) => { setFileB(f); setError(null); }} onReject={reject} />
      </div>

      <div className="actions">
        <button type="button" onClick={compare} disabled={!fileA || !fileB || loading}>
          {loading ? "Comparing…" : "Compare Certificates"}
        </button>
        {result && (
          <button type="button" className="secondary" onClick={() => downloadReport(result)}>
            Export JSON
          </button>
        )}
      </div>

      {error && <ErrorAlert message={error} />}
      {loading && <p className="muted" aria-live="polite">Reading and comparing certificates…</p>}
      {result && <DiffTable result={result} />}
    </>
  );
}
