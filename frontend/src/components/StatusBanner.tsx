import type { InspectResult, CertStatus } from "../types";

const TITLES: Record<CertStatus, { tone: string; title: string }> = {
  valid: { tone: "ok", title: "Certificate is valid and trusted" },
  expiring_soon: { tone: "warn", title: "Certificate is trusted but expiring soon" },
  expired: { tone: "bad", title: "Certificate has expired" },
  untrusted: { tone: "bad", title: "Certificate is NOT trusted" },
  hostname_mismatch: { tone: "bad", title: "Certificate does not match this hostname" },
};

function Check({ ok, label, detail }: { ok: boolean; label: string; detail?: string | null }) {
  return (
    <li className={ok ? "check ok" : "check bad"}>
      <span aria-hidden="true">{ok ? "✓" : "✗"}</span>
      <span>
        <strong>{label}:</strong> {ok ? "Yes" : "No"}
        {detail ? <em> — {detail}</em> : null}
      </span>
    </li>
  );
}

export function StatusBanner({ result }: { result: InspectResult }) {
  const { tone, title } = TITLES[result.status];
  const v = result.validation;
  return (
    <section className={`card banner banner-${tone}`} aria-label="Certificate status">
      <h2 data-testid="status-title">{title}</h2>
      <p className="muted">
        The certificate was retrieved from <code>{result.domain}</code> ({result.ip_address}).
        Retrieving a certificate does not mean it is trustworthy — see the checks below.
      </p>
      <ul className="checks">
        <Check ok={v.trusted} label="Trusted chain" detail={v.trust_error} />
        <Check ok={v.hostname_match} label="Hostname matches" detail={v.hostname_detail} />
        <Check
          ok={!result.validity.expired && !result.validity.not_yet_valid}
          label="Within validity period"
        />
      </ul>
      {result.warnings.map((w) => (
        <p key={w} className="alert alert-warn">
          {w}
        </p>
      ))}
    </section>
  );
}
