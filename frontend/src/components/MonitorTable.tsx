import type { MonitoredDomain } from "../types";
import { formatDate } from "./ExpiryCard";
import { MonitorStatusBadge } from "./MonitorStatusBadge";

interface Props {
  domains: MonitoredDomain[];
  busyId: number | null;
  selectedId: number | null;
  onCheck: (d: MonitoredDomain) => void;
  onRemove: (d: MonitoredDomain) => void;
  onSelect: (d: MonitoredDomain) => void;
}

function daysText(d: MonitoredDomain): string {
  if (d.days_remaining === null) return "—";
  if (d.days_remaining < 0) return `Expired ${Math.abs(d.days_remaining)}d ago`;
  return `${d.days_remaining} day${d.days_remaining === 1 ? "" : "s"}`;
}

export function MonitorTable({ domains, busyId, selectedId, onCheck, onRemove, onSelect }: Props) {
  if (domains.length === 0) {
    return (
      <section className="card">
        <p className="muted">No domains are being monitored yet. Add one above to get started.</p>
      </section>
    );
  }
  return (
    <section className="card" aria-label="Monitored domains">
      <div className="table-wrap">
        <table className="diff-table monitor-table">
          <thead>
            <tr>
              <th scope="col">Domain</th>
              <th scope="col">Status</th>
              <th scope="col">Issuer</th>
              <th scope="col">Expires</th>
              <th scope="col">Days left</th>
              <th scope="col">Last checked</th>
              <th scope="col"><span className="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            {domains.map((d) => {
              const busy = busyId === d.id;
              return (
                <tr key={d.id} data-testid={`row-${d.domain}`} className={selectedId === d.id ? "row-selected" : ""}>
                  <th scope="row">
                    {d.domain}
                    {d.last_error && <div className="muted small">{d.last_error}</div>}
                  </th>
                  <td><MonitorStatusBadge status={d.status} /></td>
                  <td>{d.issuer ?? "—"}</td>
                  <td>{d.not_after ? formatDate(d.not_after) : "—"}</td>
                  <td data-testid={`days-${d.domain}`}>{daysText(d)}</td>
                  <td>{d.last_checked_at ? formatDate(d.last_checked_at) : "Never"}</td>
                  <td className="row-actions">
                    <button type="button" className="small-button" disabled={busy} onClick={() => onCheck(d)}
                            aria-label={`Check ${d.domain} now`}>
                      {busy ? "Checking…" : "Check now"}
                    </button>
                    <button type="button" className="small-button secondary" onClick={() => onSelect(d)}
                            aria-label={`View history for ${d.domain}`}>
                      History
                    </button>
                    <button type="button" className="small-button danger" disabled={busy} onClick={() => onRemove(d)}
                            aria-label={`Remove ${d.domain}`}>
                      Remove
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
