# CertWatch

**A small, self-hosted toolkit for looking at TLS certificates: inspect them, compare them, and keep an eye on them.**

[![CI](https://github.com/rashmisingh261/CertWatch/actions/workflows/ci.yml/badge.svg)](https://github.com/rashmisingh261/CertWatch/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Why CertWatch?

Expired and unexpectedly replaced certificates cause outages, and the tools for checking them are either a pile of
`openssl` incantations or heavyweight monitoring platforms. CertWatch is the middle ground: a lightweight web app you
can run on your laptop or a small server that answers three everyday questions.

- **What certificate is this site serving, and can I trust it?**: Certificate Inspector
- **What exactly changed between these two certificates?**: CertDiff
- **Is anything I care about about to expire or change?**: Certificate Monitor

CertWatch is deliberately small and honest about what it does: it separates *"I could read the certificate"* from *"the
certificate is trustworthy"*, never silently disables TLS verification, and does not call every change suspicious.

## Features

| | |
|---|---|
| **Certificate Inspector** | Enter a domain; CertWatch connects on port 443 and shows subject, issuer, validity and days remaining, SANs, SHA-256 fingerprint, TLS version, cipher, key and signature algorithms. Trust (CA chain) and hostname matching are reported **separately** from retrieval. Broken certificates are still displayed, clearly flagged. |
| **CertDiff** | Upload two PEM certificates and get a side-by-side comparison of 14 attributes, each marked `UNCHANGED`, `MODIFIED`, `ADDED` or `REMOVED`, with a plain-language explanation. SANs and key usages are compared as sets. Export the result as JSON. |
| **Certificate Monitor** | Save domains, run checks on demand, and track expiry, status and certificate changes. Every check is kept in an append-only history that shows exactly what changed. Stored locally in SQLite. |

Security is part of the design, not an afterthought: SSRF and DNS-rebinding protection, port 443 only, timeouts, rate
limiting, and strict upload validation (see [Security](#security)).

## Screenshots

Screenshots are produced from generated certificates and documentation-only domains (`example.com` and friends); no
real hosts, keys or secrets. See [docs/demo.md](docs/demo.md) for the walkthrough and how to reproduce them in a minute:

```bash
backend/.venv/bin/python scripts/demo.py serve      # demo backend with generated certificates
cd frontend && npm run dev                          # UI on http://localhost:5173
```

<!--
After capturing (see docs/screenshots/README.md), uncomment:
![Inspector](docs/screenshots/inspector.png)
![CertDiff](docs/screenshots/certdiff.png)
![Monitor](docs/screenshots/monitor.png)
-->

## Architecture

```
 Browser ──► React + TypeScript (Vite)
               │  /api/*  (Vite proxy in dev, nginx in Docker)
               ▼
            FastAPI ── api/       inspect · certdiff · monitor   (thin HTTP routes)
               │       core/      validation · network_guard (SSRF) · rate_limit · upload_limit · errors
               │       services/  inspector · certdiff · monitor · runner
               │            │
               │            ├──► DNS (resolved once, every address checked) ──► TLS on port 443 only
               ▼            ▼
            cryptography   SQLite  (monitored domains + append-only observation history)
```

- **One inspection path.** The Inspector and the Monitor both go through `services/runner.py`, which applies the same
  validation, SSRF checks, timeouts and global concurrency cap.
- **Single SQLite file**, accessed with the standard library (`sqlite3`): no ORM, no external services, no queue.
- **Stateless otherwise**: CertDiff keeps nothing; uploads are processed in memory.

## Technology

| Layer | Stack |
|---|---|
| Backend | Python 3.10+, FastAPI, `cryptography`, SQLite, `certifi` (CA bundle) |
| Frontend | React 18, TypeScript, Vite |
| Tests | Pytest · Vitest + Testing Library |
| Quality | Ruff · ESLint · GitHub Actions |
| Packaging | Docker, Docker Compose, nginx |

## Prerequisites

- **Docker route:** Docker with the Compose plugin.
- **Local route:** Python **3.10 or newer** (older versions cannot install the patched dependency versions) and
  Node.js **20 or newer**.

## Installation

### Option 1: Docker (recommended)

```bash
git clone https://github.com/rashmisingh261/CertWatch.git
cd CertWatch
docker compose up --build
```

Open **http://localhost:8080**.

- The monitor database lives in the `certwatch-data` Docker volume and survives restarts and rebuilds.
  `docker compose down` keeps it; `docker compose down --volumes` deletes it.
- The UI is published on **127.0.0.1 only**, because the Monitor API has no authentication. To use another port, copy
  `.env.example` to `.env` and set `CERTWATCH_PORT`.
- The backend container is not published; only the nginx frontend can reach it.

### Option 2: Local development

**Backend**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
uvicorn app.main:app --port 8000     # add --reload while developing
```

**Frontend** (second terminal)

```bash
cd frontend
npm ci
npm run dev                          # http://localhost:5173
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`; no CORS setup or `.env` file is needed. The monitor
database is created at `backend/data/certwatch.db` on first start (git-ignored).

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `CERTWATCH_DB_PATH` | `backend/data/certwatch.db` (`/data/certwatch.db` in Docker) | SQLite file location |
| `CERTWATCH_PORT` | `8080` | Docker only: host port for the web UI (set in `.env`) |

CertWatch needs no secrets and reads no credentials. Operational limits (timeouts, rate limits, upload size, the
100-domain monitor cap) are constants in [backend/app/core/config.py](backend/app/core/config.py).

## Usage

### Certificate Inspector

Enter a domain such as `example.com` and click **Inspect**. The result reports:

- Subject, issuer, validity dates, days remaining, SANs, SHA-256 fingerprint, TLS version, cipher, key and signature algorithms.
- **Trusted chain**: verified against the Mozilla CA bundle (`certifi`).
- **Hostname matches**: checked against the certificate's SANs.
- **Within validity period**.

A certificate that fails verification (expired, self-signed, wrong host, unknown CA) is still **displayed**, but it is
always flagged as not trusted and the reason is shown.

### CertDiff

1. Open the **CertDiff** tab and choose a PEM certificate for **Certificate A** and **Certificate B**.
2. Click **Compare Certificates**.
3. Review the side-by-side table. **Details** on a row explains the difference; **Show differences only** hides unchanged rows.
4. **Export JSON** downloads the report.

Compared attributes: Subject, Issuer, Serial number, Valid from, Valid until, Signature algorithm, Public key algorithm,
Public key size, Public key fingerprint, Certificate SHA-256 fingerprint, Subject Alternative Names, Basic Constraints,
Key Usage, Extended Key Usage. Missing optional extensions are handled (shown as "not present").

| Status | Meaning |
|---|---|
| `UNCHANGED` | Same in both |
| `MODIFIED` | In both, but different |
| `ADDED` | Only in Certificate B |
| `REMOVED` | Only in Certificate A |

List fields are compared as sets:

```
A: example.com, www.example.com        B: example.com, api.example.com
→ unchanged: example.com   removed: www.example.com   added: api.example.com
```

A different certificate fingerprint is expected whenever anything differs (a routine renewal, for instance) and is **not**
treated as a security problem. To get a PEM file from a live site:

```bash
openssl s_client -connect example.com:443 -servername example.com </dev/null 2>/dev/null | openssl x509 > example.pem
```

### Certificate Monitor

1. Open the **Monitor** tab, enter a domain and click **Add Domain**. It is validated, checked once, and saved.
2. The table shows issuer, expiry, days remaining, last checked and **status**.
3. **Check now** re-checks; **History** shows every observation and what changed; **Remove** deletes the domain and its history.

Checks are **manual**; there is no scheduler or notification system in 1.0.

**Statuses** are evaluated when a check completes; the first matching rule wins:

| # | Status | Meaning |
|---|---|---|
| 1 | `CHECK_FAILED` | The check itself failed (DNS, connection, timeout, TLS handshake). Last known certificate details are kept. |
| 2 | `EXPIRED` | Past its expiry date |
| 3 | `INVALID` | Chain not trusted, hostname mismatch, or not yet valid |
| 4 | `CHANGED` | Fingerprint differs from the previous *successful* observation |
| 5 | `EXPIRING_SOON` | 30 days or less remaining |
| 6 | `HEALTHY` | Valid, trusted, hostname matches, more than 30 days remaining |

- A changed certificate that is also expired shows `EXPIRED`; the change is still recorded in its history entry.
- `CHANGED` describes the latest check; after the next unchanged check the status returns to `HEALTHY`, but the change stays in the history and the "last changed" timestamp.
- Statuses are also *aged* when displayed: a domain last checked as `HEALTHY` shows `EXPIRING_SOON`, then `EXPIRED`, as its date approaches, even without a new check.

**Change detection:** when the fingerprint differs, CertWatch lists exactly what changed (subject, issuer, serial, validity,
signature algorithm, public key and its fingerprint, SANs added/removed) with a neutral explanation such as *"same issuer
and public key, consistent with a routine renewal"*. History is append-only; a change adds an entry and never overwrites
the previous one. Only parsed attributes are stored: no PEM/DER bytes or keys.

When adding a domain: invalid names (`422`) and names resolving to non-public addresses (`403`) are rejected; a name that
does not resolve (`502`, usually a typo) is not saved; a host that resolves but cannot be reached is saved as `CHECK_FAILED`;
duplicates (after normalisation) return `409` without any network connection.

## API

Errors always have the shape `{"error": {"code": "...", "message": "..."}}`. Interactive docs are served at `/docs`
when running the backend directly.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/inspect` | Inspect a domain: `{"domain": "example.com"}` |
| `POST` | `/api/certdiff` | Compare two PEM files (`multipart/form-data`: `certificate_a`, `certificate_b`) |
| `POST` | `/api/monitor` | Add a domain and run its first check → `201` |
| `GET` | `/api/monitor` | List monitored domains |
| `GET` | `/api/monitor/{id}` | Details and full observation history (newest first) |
| `POST` | `/api/monitor/{id}/check` | Run a manual check |
| `DELETE` | `/api/monitor/{id}` | Remove the domain and its history → `204` |

Common error codes: `invalid_domain` (422), `blocked_address` (403), `dns_error` / `connection_failed` / `tls_error` (502),
`timeout` (504), `rate_limited` (429), `busy` (503), `invalid_certificate` (422), `file_too_large` (413),
`duplicate_domain` / `limit_reached` (409), `not_found` (404).

### Examples

```bash
# Inspect a domain
curl -s -X POST http://localhost:8000/api/inspect \
  -H 'Content-Type: application/json' -d '{"domain": "example.com"}'

# Compare two certificates
curl -s -F certificate_a=@old.pem -F certificate_b=@new.pem http://localhost:8000/api/certdiff

# Monitor a domain, re-check it, read its history, remove it
curl -s -X POST http://localhost:8000/api/monitor -H 'Content-Type: application/json' -d '{"domain": "example.com"}'
curl -s -X POST http://localhost:8000/api/monitor/1/check
curl -s http://localhost:8000/api/monitor/1
curl -s -X DELETE http://localhost:8000/api/monitor/1
```

(With Docker, use port `8080` instead of `8000`.)

## Testing

```bash
# Backend: lint + tests (no network access needed; TLS and DNS are mocked with generated certificates)
cd backend && source .venv/bin/activate
ruff check --config pyproject.toml . ../scripts
pytest

# Frontend: lint + tests + production build
cd frontend
npm run lint && npm test && npm run build
```

All tests run offline. CI runs the same checks on every push to `main` and every pull request, and also builds and
smoke-tests the Docker setup.

## Security

CertWatch makes outbound connections on behalf of its users, so it is built to avoid becoming a proxy into internal networks.
Full details and the reporting process are in [SECURITY.md](SECURITY.md). In short:

- **SSRF:** input must be a bare fully-qualified domain name (no URLs, ports, IP literals). The port is a constant (443).
  DNS is resolved once; if *any* answer is private, loopback, link-local, multicast, reserved, carrier-grade NAT or an
  embedded-IPv4 transition address, the request is refused.
- **DNS rebinding:** the TCP connection goes to the already-validated IP, never to the hostname, so a second DNS answer cannot redirect it.
  SNI and hostname matching still use the original name.
- **Resource limits:** timeouts on DNS, connect and handshake; an overall deadline; a global concurrency cap; per-client rate limits; a per-domain cooldown for manual checks.
- **Uploads (CertDiff):** 1 MB per file enforced on declared and received bytes; PEM only; private keys rejected; processed in memory, never stored or echoed.
- **TLS verification is never silently disabled.** Where an unverified read is needed to *display* a broken certificate, the result is always reported as untrusted with the reason.

## Limitations

- **No authentication.** The Monitor API is for local, single-user use. Docker publishes the UI on `127.0.0.1` only; put it behind an authenticating reverse proxy before exposing it more widely.
- **Port 443 only**, direct TLS only (no STARTTLS, no other ports, no client certificates). Servers that only support TLS 1.0/1.1 cannot be inspected.
- **Leaf certificate only.** The Inspector reports the server's certificate; it does not display the intermediate chain.
- **Trust uses the Mozilla CA bundle** (`certifi`), not your operating system's store. Certificates issued by a private/corporate CA appear as untrusted.
- **Public hosts only.** Internal and private-network hosts are blocked by design, so CertWatch cannot monitor them.
- **Manual checks only.** No scheduler, no notifications.
- **CertDiff accepts PEM only**, exactly one certificate per file (no DER, PKCS#12 or chain bundles).
- **Rate limits are in memory and per process.** With several workers each keeps its own counters.
- **SQLite** suits a single instance; there is no migration tooling yet (the schema is created if missing).

## Roadmap

Ideas, not commitments:

- Scheduled background checks and notifications (email / webhook)
- Show the full certificate chain and intermediate expiry
- Optional authentication for shared deployments
- DER and chain-bundle support in CertDiff
- Exporting monitor history

## Project layout

```
backend/
  app/
    api/         inspect.py, certdiff.py, monitor.py       # HTTP routes
    core/        config, validation, network_guard, rate_limit, upload_limit, errors
    services/    inspector, hostname, certdiff, monitor, runner, certutil
    db.py                                                   # SQLite schema + connections
    schemas*.py                                             # response models
  tests/
frontend/src/    pages/ · components/ · api/ · lib/
scripts/demo.py  demo data for screenshots (generated certificates; not part of the app)
docs/            demo walkthrough and screenshot checklist
```

## Contributing

Contributions are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). Release history is in [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).
