import type { InspectResult, Name } from "../types";

function NameBlock({ title, name }: { title: string; name: Name }) {
  return (
    <section className="card" aria-label={title}>
      <h3>{title}</h3>
      <dl>
        <dt>Common name</dt>
        <dd>{name.common_name ?? "—"}</dd>
        <dt>Organization</dt>
        <dd>{name.organization ?? "—"}</dd>
        <dt>Full DN</dt>
        <dd className="mono">{name.rfc4514}</dd>
      </dl>
    </section>
  );
}

export function CertDetails({ result }: { result: InspectResult }) {
  return (
    <>
      <div className="grid">
        <NameBlock title="Subject" name={result.subject} />
        <NameBlock title="Issuer" name={result.issuer} />
      </div>

      <section className="card" aria-label="Subject Alternative Names">
        <h3>Subject Alternative Names ({result.sans.length})</h3>
        {result.sans.length === 0 ? (
          <p className="muted">None.</p>
        ) : (
          <ul className="sans">
            {result.sans.map((s) => (
              <li key={s} className="mono">
                {s}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card" aria-label="Technical details">
        <h3>Technical details</h3>
        <dl>
          <dt>TLS version</dt>
          <dd data-testid="tls-version">{result.tls_version}</dd>
          <dt>Cipher</dt>
          <dd className="mono">{result.cipher ?? "—"}</dd>
          <dt>SHA-256 fingerprint</dt>
          <dd className="mono" data-testid="fingerprint">
            {result.fingerprint_sha256}
          </dd>
          <dt>Public key</dt>
          <dd>{result.public_key}</dd>
          <dt>Signature algorithm</dt>
          <dd>{result.signature_algorithm ?? "—"}</dd>
          <dt>Serial number</dt>
          <dd className="mono">{result.serial_number}</dd>
        </dl>
      </section>
    </>
  );
}
