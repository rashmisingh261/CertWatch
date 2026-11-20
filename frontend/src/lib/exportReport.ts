import type { DiffResult, FieldDiff } from "../types";

/** Build the exported report from a comparison. Contains parsed attributes only. */
export function buildReport(result: DiffResult) {
  const f = (s: FieldDiff["status"]) => result.fields.filter((x) => x.status === s);
  return {
    report: "CertWatch CertDiff",
    compared_at: result.compared_at,
    certificate_a: result.certificate_a,
    certificate_b: result.certificate_b,
    summary: result.summary,
    comparison: result.fields.map(({ key, label, status, a, b, added, removed, unchanged, explanation }) => ({
      key, label, status, certificate_a: a, certificate_b: b, added, removed, unchanged, explanation,
    })),
    // Convenience groupings of the same data:
    added_values: result.fields
      .filter((x) => x.status === "ADDED" || x.added.length > 0)
      .map((x) => ({ field: x.label, values: x.kind === "list" ? x.added : [x.b] })),
    removed_values: result.fields
      .filter((x) => x.status === "REMOVED" || x.removed.length > 0)
      .map((x) => ({ field: x.label, values: x.kind === "list" ? x.removed : [x.a] })),
    modified_values: f("MODIFIED").map((x) => ({ field: x.label, certificate_a: x.a, certificate_b: x.b })),
    unchanged_values: f("UNCHANGED").map((x) => ({
      field: x.label,
      value: x.kind === "list" ? x.unchanged : x.a,
    })),
  };
}

export function downloadReport(result: DiffResult): void {
  const blob = new Blob([JSON.stringify(buildReport(result), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `certdiff-${result.compared_at.replace(/[:.]/g, "-")}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
