import type { MonitoredDomainDetail, Observation } from "../types";
import { formatDate } from "./ExpiryCard";
import { MonitorStatusBadge } from "./MonitorStatusBadge";

function Changes({ obs }: { obs: Observation }) {
  const c = obs.changes;
  if (!c) return null;
  return (
    <div className="change-box" data-testid="change-box">
      <strong>🔄 Certificate changed since the previous observation</strong>
      <p className="muted small">{c.hint}</p>
      <ul className="change-list">
        {c.fields.map((f) => (
          <li key={f.key}>
            <span className="change-label">{f.label}</span>
            <span className="mono old">{f.before ?? "—"}</span>
            <span aria-hidden="true"> → </span>
            <span className="mono new">{f.after ?? "—"}</span>
          </li>
        ))}
      </ul>
      {(c.sans_added.length > 0 || c.sans_removed.length > 0) && (
        <ul className="chips">
          {c.sans_removed.map((s) => <li key={`r-${s}`} className="chip chip-removed">－ {s}</li>)}
          {c.sans_added.map((s) => <li key={`a-${s}`} className="chip chip-added">＋ {s}</li>)}
        </ul>
      )}
    </div>
  );
}

function Entry({ obs }: { obs: Observation }) {
  return (
    <li className={`timeline-item${obs.changed ? " is-change" : ""}${obs.outcome === "failed" ? " is-failed" : ""}`}
        data-testid="observation">
      <div className="timeline-head">
        <strong>{formatDate(obs.observed_at)}</strong>
        <MonitorStatusBadge status={obs.status} />
      </div>
      {obs.outcome === "failed" ? (
        <p className="muted">Check failed: {obs.error_message}</p>
      ) : (
        <dl>
          <dt>SHA-256 fingerprint</dt>
          <dd className="mono" data-testid="obs-fingerprint">{obs.fingerprint_sha256}</dd>
          <dt>Issuer</dt>
          <dd className="mono">{obs.issuer}</dd>
          <dt>Valid until</dt>
          <dd>{obs.not_after ? formatDate(obs.not_after) : "—"}</dd>
          <dt>TLS version</dt>
          <dd>{obs.tls_version}</dd>
          {obs.trusted === false && (<><dt>Trust</dt><dd>Not trusted: {obs.trust_error}</dd></>)}
          {obs.hostname_match === false && (<><dt>Hostname</dt><dd>Does not match the certificate</dd></>)}
        </dl>
      )}
      <Changes obs={obs} />
    </li>
  );
}

export function MonitorHistory({ detail, onClose }: { detail: MonitoredDomainDetail; onClose: () => void }) {
  return (
    <section className="card" aria-label={`History for ${detail.domain}`}>
      <div className="history-head">
        <h3>History: {detail.domain}</h3>
        <button type="button" className="link-button" onClick={onClose}>Close</button>
      </div>
      <p className="muted small">
        Every check is recorded. A new certificate adds an entry; earlier entries are never overwritten.
        Changes are normal when a certificate is renewed.
      </p>
      <ol className="timeline">
        {detail.observations.map((o) => <Entry key={o.id} obs={o} />)}
      </ol>
    </section>
  );
}
