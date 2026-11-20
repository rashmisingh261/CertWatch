# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Optional `CERTWATCH_BIND` setting so the Docker UI can be published on a Tailscale/VPN address without editing
  `docker-compose.yml`. The default remains `127.0.0.1`.
- README: private-demo notice and an "Accessing CertWatch" section covering local access and private access over Tailscale.
- CI check that the UI is published on loopback only and that the backend port is not published.

## [1.0.0] - 2026-11-20

First stable release.

### Added

- **Certificate Inspector**: inspect the certificate served on port 443 by any public domain: subject, issuer, validity and
  days remaining, Subject Alternative Names, SHA-256 fingerprint, public key fingerprint, TLS version, cipher, key and
  signature algorithms. Chain trust and hostname matching are reported separately from retrieval; certificates that fail
  verification are still displayed, flagged as untrusted with the reason.
- **CertDiff**: upload two PEM certificates and compare 14 attributes as `UNCHANGED`, `MODIFIED`, `ADDED` or `REMOVED`, with
  set-based comparison of SANs, Key Usage and Extended Key Usage, plain-language explanations and JSON export.
- **Certificate Monitor**: save domains, run manual checks, and track expiry and certificate changes. Statuses: `HEALTHY`,
  `EXPIRING_SOON`, `EXPIRED`, `INVALID`, `CHECK_FAILED`, `CHANGED`. Append-only observation history in SQLite shows exactly
  what changed; statuses age with time between checks.
- React + TypeScript web interface with a responsive pastel design.
- Docker setup (`docker compose up --build`) with a persistent SQLite volume, non-root containers and health checks.
- GitHub Actions CI: Ruff + Pytest (Python 3.11 and 3.12), ESLint + Vitest + build (Node 22), and a Docker build and smoke test.
- `scripts/demo.py` to run the app against generated certificates for documentation-only domains (screenshots and demos).
- Documentation: README, CONTRIBUTING, SECURITY and a demo walkthrough.

### Security

- SSRF protection: bare fully-qualified domain names only; port fixed to 443; every resolved address must be public
  (private, loopback, link-local, multicast, reserved, CGNAT and IPv6 transition ranges are blocked).
- DNS-rebinding mitigation: DNS is resolved once and the connection goes to the validated IP.
- Timeouts, an overall deadline, a global concurrency cap, per-client rate limits and a per-domain check cooldown.
- CertDiff upload hardening: 1 MB limit enforced on declared and received bytes, PEM only, private keys rejected, nothing
  stored or echoed back.
- Unparseable certificates presented by a remote server produce a clean error (and a recorded failed check in the Monitor)
  instead of an internal error.
- Dependencies audited: no known vulnerabilities in the Python or npm dependency sets at release. Python 3.11+ is
  required (3.10 is end-of-life) so that patched `starlette`, `python-multipart` and `anyio` releases can be installed.

### Known limitations

No authentication (local single-user use), port 443 only, leaf certificate only, manual checks only. See the README.
