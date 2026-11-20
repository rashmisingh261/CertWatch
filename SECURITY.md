# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | ✅ Security fixes |
| < 1.0 | ❌ Pre-release |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately using GitHub's *Report a vulnerability* feature: open the repository's **Security** tab →
**Report a vulnerability** (<https://github.com/rashmisingh261/CertWatch/security/advisories/new>).

Please include what you found, the steps or request needed to reproduce it, the affected version/commit, and the impact you
expect. A proof of concept that uses only your own systems is ideal; do not test against infrastructure you do not own.

This is a volunteer-maintained project. We aim to acknowledge reports within a few days, keep you updated, and credit you in
the release notes if you wish. Please allow time for a fix before any public disclosure.

## What CertWatch is designed to protect

CertWatch connects to hosts named by its users, so the main risk is it being abused as a network proxy. Reports about any
of the following are especially welcome:

- Bypassing the **SSRF protections**: reaching private, loopback, link-local, multicast, reserved or cloud-metadata addresses (IPv4 or IPv6, including mapped/transition forms), or any port other than 443.
- **DNS rebinding** or TOCTOU between address validation and connection.
- Domain-validation bypasses (URLs, IP literals, odd encodings).
- Escaping the **resource limits** (timeouts, concurrency cap, rate limits, upload size).
- Crashes or resource exhaustion from malformed certificates or uploads in CertDiff, the Inspector or the Monitor.
- Injection, path traversal or information disclosure (for example stack traces or file contents in responses).
- Vulnerable or insecurely configured dependencies and container images.

## Security expectations and known boundaries

- **No authentication.** The Monitor API and the rest of the app are designed for local, single-user use. The Docker setup publishes the UI on `127.0.0.1` only. If you expose CertWatch to a network, put it behind an authenticating reverse proxy and TLS. Missing authentication on its own is a documented limitation, not a vulnerability.
- **Rate limits are in memory and per process**; they deter casual abuse but are not a substitute for network-level protection.
- **TLS verification is never silently disabled.** The Inspector may complete a handshake *without* verification solely to display a certificate that failed verification, and always reports it as untrusted with the reason.
- **Trust decisions use the Mozilla CA bundle (`certifi`)**, not the operating system's store.
- CertWatch stores only parsed certificate attributes (never keys, PEM or DER) in a local SQLite file, and never stores uploaded CertDiff files.
- **Never upload private keys** to CertWatch or any other tool. CertDiff rejects PEM files containing private keys.

## For deployers

- Keep dependencies and the base images up to date; CI builds on every change, and `pip-audit` / `npm audit` are quick to run locally.
- Do not publish the backend port directly; use the provided Compose file, where only the nginx frontend is exposed.
