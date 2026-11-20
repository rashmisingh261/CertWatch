import type { Validity } from "../types";

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }) + " UTC";
}

export function ExpiryCard({ validity }: { validity: Validity }) {
  const d = validity.days_remaining;
  const tone = validity.expired ? "bad" : d < 30 ? "warn" : "ok";
  const text = validity.expired
    ? `Expired ${Math.abs(d)} day${Math.abs(d) === 1 ? "" : "s"} ago`
    : `${d} day${d === 1 ? "" : "s"} remaining`;
  return (
    <section className="card" aria-label="Expiry">
      <h3>Expiry</h3>
      <p className={`big big-${tone}`} data-testid="days-remaining">
        {text}
      </p>
      <dl>
        <dt>Valid from</dt>
        <dd>{formatDate(validity.not_before)}</dd>
        <dt>Valid until</dt>
        <dd>{formatDate(validity.not_after)}</dd>
      </dl>
    </section>
  );
}
