import { useState } from "react";
import type { DiffResult, DiffStatus, FieldDiff } from "../types";

const BADGES: Record<DiffStatus, { icon: string; text: string }> = {
  UNCHANGED: { icon: "＝", text: "Unchanged" },
  MODIFIED: { icon: "≠", text: "Modified" },
  ADDED: { icon: "＋", text: "Added" },
  REMOVED: { icon: "－", text: "Removed" },
};

export function StatusBadge({ status }: { status: DiffStatus }) {
  const b = BADGES[status];
  return (
    <span className={`badge badge-${status.toLowerCase()}`}>
      <span aria-hidden="true">{b.icon}</span> {b.text}
    </span>
  );
}

function Cell({ field, side }: { field: FieldDiff; side: "a" | "b" }) {
  const value = side === "a" ? field.a : field.b;
  if (field.kind === "list") {
    const own = side === "a" ? field.removed : field.added;
    const items = [...(value as string[] | null ?? [])];
    if (items.length === 0) return <span className="muted">— none —</span>;
    return (
      <ul className="chips">
        {items.map((v) => {
          const marker = own.includes(v) ? (side === "a" ? "removed" : "added") : "same";
          return (
            <li key={v} className={`chip chip-${marker}`} title={marker === "same" ? "In both" : marker === "removed" ? "Only in A" : "Only in B"}>
              {marker === "removed" ? "－ " : marker === "added" ? "＋ " : ""}
              {v}
            </li>
          );
        })}
      </ul>
    );
  }
  if (value === null || value === undefined) return <span className="muted">— not present —</span>;
  return <span className="mono value">{value as string}</span>;
}

function Row({ field }: { field: FieldDiff }) {
  const [open, setOpen] = useState(false);
  const detailId = `detail-${field.key}`;
  return (
    <>
      <tr className={`row-${field.status.toLowerCase()}`} data-testid={`row-${field.key}`}>
        <th scope="row">
          {field.label}
          <button
            type="button"
            className="link-button details-toggle"
            aria-expanded={open}
            aria-controls={detailId}
            onClick={() => setOpen(!open)}
          >
            {open ? "Hide details" : "Details"}
          </button>
        </th>
        <td><StatusBadge status={field.status} /></td>
        <td><Cell field={field} side="a" /></td>
        <td><Cell field={field} side="b" /></td>
      </tr>
      {open && (
        <tr className="detail-row" id={detailId}>
          <td colSpan={4}>
            <p><strong>What this means:</strong> {field.explanation}</p>
            {field.kind === "list" ? (
              <dl>
                <dt>Unchanged</dt><dd>{field.unchanged.join(", ") || "—"}</dd>
                <dt>Removed (only in A)</dt><dd>{field.removed.join(", ") || "—"}</dd>
                <dt>Added (only in B)</dt><dd>{field.added.join(", ") || "—"}</dd>
              </dl>
            ) : (
              <dl>
                <dt>Certificate A</dt><dd className="mono">{(field.a as string | null) ?? "—"}</dd>
                <dt>Certificate B</dt><dd className="mono">{(field.b as string | null) ?? "—"}</dd>
              </dl>
            )}
          </td>
        </tr>
      )}
    </>
  );
}

export function DiffTable({ result }: { result: DiffResult }) {
  const [filter, setFilter] = useState<"all" | "changes">("all");
  const rows = filter === "all" ? result.fields : result.fields.filter((f) => f.status !== "UNCHANGED");
  return (
    <section className="card" aria-label="Comparison">
      <div className="diff-toolbar">
        <ul className="summary-pills" aria-label="Summary">
          {(Object.keys(BADGES) as DiffStatus[]).map((s) => (
            <li key={s} className={`badge badge-${s.toLowerCase()}`} data-testid={`count-${s}`}>
              {BADGES[s].text}: {result.summary[s]}
            </li>
          ))}
        </ul>
        <label className="toggle">
          <input
            type="checkbox"
            checked={filter === "changes"}
            onChange={(e) => setFilter(e.target.checked ? "changes" : "all")}
          />
          Show differences only
        </label>
      </div>
      <div className="table-wrap">
        <table className="diff-table">
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Status</th>
              <th scope="col">Certificate A<br /><span className="muted">{result.certificate_a.filename}</span></th>
              <th scope="col">Certificate B<br /><span className="muted">{result.certificate_b.filename}</span></th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr><td colSpan={4} className="muted">No differences found.</td></tr>
            ) : (
              rows.map((f) => <Row key={f.key} field={f} />)
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
