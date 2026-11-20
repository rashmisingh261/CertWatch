# CertWatch

**A small, self-hosted toolkit for looking at TLS certificates: inspect them, compare them, and keep an eye on them.**

[![CI](https://github.com/rashmisingh261/CertWatch/actions/workflows/ci.yml/badge.svg)](https://github.com/rashmisingh261/CertWatch/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **Private demo.** CertWatch has **no authentication**. It is intended for private use only: on your own machine, or
> from your own devices over a private network or VPN such as Tailscale. **Do not expose it to the public internet
> without authentication in front of it.** See [Accessing CertWatch](#accessing-certwatch-private-demo) and
> [Deployment and Security Considerations](#deployment-and-security-considerations).

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
| Backend | Python 3.11+, FastAPI, `cryptography`, SQLite, `certifi` (CA bundle) |
| Frontend | React 18, TypeScript, Vite |
| Tests | Pytest · Vitest + Testing Library |
| Quality | Ruff · ESLint · GitHub Actions |
| Packaging | Docker, Docker Compose, nginx |

## Prerequisites

- **Docker route:** Docker with the Compose plugin.
- **Local route:** Python **3.11 or newer** (older versions are end-of-life and cannot install the patched dependency versions) and
  Node.js **22 or newer**.

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
- The UI is published on **127.0.0.1 only** by default, because CertWatch has no authentication. To reach it from your
  other devices privately, see [Accessing CertWatch](#accessing-certwatch-private-demo). To use another port, copy
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
| `CERTWATCH_BIND` | `127.0.0.1` | Docker only: address the web UI is published on (set in `.env`). Leave at the default, or use your Tailscale address; never `0.0.0.0` |
| `CERTWATCH_PORT` | `8080` | Docker only: host port for the web UI (set in `.env`) |

CertWatch needs no secrets and reads no credentials. Operational limits (timeouts, rate limits, upload size, the
100-domain monitor cap) are constants in [backend/app/core/config.py](backend/app/core/config.py).

## Accessing CertWatch (private demo)

CertWatch is meant to be used **privately**: on the machine it runs on, or from your own devices over a private network
such as [Tailscale](https://tailscale.com). It is never meant to be reachable from the public internet.

### On the same machine

| How you started it | Open |
|---|---|
| `docker compose up --build` | **http://localhost:8080** |
| Local development (backend + `npm run dev`) | **http://localhost:5173** |

In both cases the servers listen on `127.0.0.1` only, so other computers cannot reach them. With Docker, the backend is
not published at all; only the web container can talk to it. Stop CertWatch with `docker compose down` (your monitored
domains are kept in the `certwatch-data` volume).

### From your other devices, privately, with Tailscale

Tailscale builds an encrypted private network (a *tailnet*) between your own devices. Only devices signed in to your
tailnet can reach CertWatch, and nothing is exposed to the internet.

**One-time setup:** install Tailscale on the machine that runs CertWatch and on each device you want to use, and sign in
to the same tailnet on all of them.

**Option A: Tailscale Serve (recommended).** No CertWatch configuration changes; it keeps the UI bound to
`127.0.0.1` and lets Tailscale forward your tailnet's traffic to it over HTTPS:

```bash
docker compose up -d --build
tailscale serve --bg 8080
tailscale serve status          # prints the address, e.g. https://my-machine.my-tailnet.ts.net
```

Open that address from any device on your tailnet. (HTTPS must be enabled for your tailnet in the Tailscale admin
console.) To stop sharing: `tailscale serve reset`.

**Option B: bind to the Tailscale address.** Publish the UI on this machine's Tailscale address instead of the loopback
address:

```bash
tailscale ip -4                 # for example 100.101.102.103
cp .env.example .env            # then set CERTWATCH_BIND to that address in .env
docker compose up -d --build
```

Open `http://100.101.102.103:8080` (or `http://<machine-name>:8080` if MagicDNS is on). The traffic is encrypted by
Tailscale even though the URL says `http`. Start Tailscale *before* Docker, otherwise Docker cannot bind to the address.
If binding fails on Docker Desktop (macOS/Windows), use Option A.

**Never do any of these** (each one makes CertWatch reachable without a login):

- run `tailscale funnel`: it publishes the service to the **public internet**;
- set `CERTWATCH_BIND=0.0.0.0`, forward a router port to CertWatch, or open its port in a cloud firewall;
- publish the backend port (8000).

To limit which of your tailnet's devices and users can reach the machine, use
[Tailscale ACLs](https://tailscale.com/kb/1018/acls).

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
Deployment guidance (including why it must not be exposed publicly without access controls) is in
[Deployment and Security Considerations](#deployment-and-security-considerations); the reporting process is in
[SECURITY.md](SECURITY.md). In short:

- **SSRF:** input must be a bare fully-qualified domain name (no URLs, ports, IP literals). The port is a constant (443).
  DNS is resolved once; if *any* answer is private, loopback, link-local, multicast, reserved, carrier-grade NAT or an
  embedded-IPv4 transition address, the request is refused.
- **DNS rebinding:** the TCP connection goes to the already-validated IP, never to the hostname, so a second DNS answer cannot redirect it.
  SNI and hostname matching still use the original name.
- **Resource limits:** timeouts on DNS, connect and handshake; an overall deadline; a global concurrency cap; per-client rate limits; a per-domain cooldown for manual checks.
- **Uploads (CertDiff):** 1 MB per file enforced on declared and received bytes; PEM only; private keys rejected; processed in memory, never stored or echoed.
- **TLS verification is never silently disabled.** Where an unverified read is needed to *display* a broken certificate, the result is always reported as untrusted with the reason.

## Deployment and Security Considerations

> **CertWatch has no authentication and must not be exposed to the public internet without access controls.**
> It is designed for a single trusted user on a laptop, a private network or behind a VPN. The default Docker setup
> publishes the UI on `127.0.0.1` only, for exactly this reason.

### What anyone who can reach the app can do

There are no accounts, sessions or API keys. Anyone who can send requests to CertWatch can:

- make **your server** open TLS connections to any public host on port 443 (Inspector, Monitor);
- add, check and delete monitored domains and read their full history (Monitor);
- upload files for the server to parse (CertDiff);
- use up the server's worker capacity (see [Rate limits](#are-the-rate-limits-and-domain-restrictions-enough)).

### Recommended ways to deploy

Pick **one** of these. They are listed from simplest to most flexible.

**1. Local only (default).** `docker compose up --build` binds the UI to `127.0.0.1:8080`. Nothing else can reach it.

**2. Private network or VPN.** Run CertWatch on a machine that is only reachable over a private network or VPN
(Tailscale, WireGuard or similar). For Tailscale, the exact steps are in
[Accessing CertWatch](#accessing-certwatch-private-demo). With any other VPN or private network, set `CERTWATCH_BIND`
in `.env` to that interface's address (never `0.0.0.0`), and add a host firewall rule so the port is not reachable from
other networks.

**3. Reverse proxy with authentication.** Keep CertWatch bound to `127.0.0.1` and put an authenticating TLS proxy in
front of it. Anything that adds real authentication is fine (basic auth, an OIDC proxy such as oauth2-proxy or
Authelia, Cloudflare Access, ...). Two minimal examples:

```
# Caddy (v2.8+; older versions call the directive `basicauth`) - automatic HTTPS
certwatch.example.org {
    basic_auth {
        # generate the hash with:  caddy hash-password
        alice  <password-hash>
    }
    reverse_proxy 127.0.0.1:8080
}
```

```nginx
# nginx on the host (htpasswd -c /etc/nginx/certwatch.htpasswd alice)
server {
    listen 443 ssl;
    server_name certwatch.example.org;
    # ssl_certificate / ssl_certificate_key ...

    auth_basic           "CertWatch";
    auth_basic_user_file /etc/nginx/certwatch.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
    }
}
```

Notes for proxy deployments:

- **Never publish the backend (port 8000).** The Compose file sets `FORWARDED_ALLOW_IPS=*` so the backend trusts the
  client address that CertWatch's own nginx container passes along. That is safe only because the backend is reachable
  solely from that container. If port 8000 is ever reachable directly, anyone can send a fake `X-Forwarded-For` header
  and get a fresh rate-limit budget on every request.
- **Rate limits behind your own proxy.** CertWatch's nginx container reports the address it was contacted from. Behind
  another proxy, every user therefore appears as that proxy and **shares one rate-limit budget**. If you need per-user
  limits, add `set_real_ip_from <your proxy's address as seen by the container>;` and `real_ip_header X-Forwarded-For;`
  to `frontend/nginx.conf`.
- Always terminate TLS at the proxy when it is reachable over an untrusted network; basic auth over plain HTTP is not
  protection.
- The interactive API docs (`/docs`) exist only on the backend, which the proxy setup does not expose.

### Risks of server-side TLS connections

CertWatch's job is to connect, from your server, to hostnames chosen by whoever uses it. That is inherently
sensitive, even with the protections below:

| Risk | What it means |
|---|---|
| **SSRF** | An attacker tries to make the server reach internal services (admin panels, databases, cloud metadata such as `169.254.169.254`) by supplying a name or address that points inside your network. |
| **Probing of public hosts** | Anyone can create a DNS name pointing at *any* public IP, so CertWatch can be used to test whether port 443 is open on a public host. The different outcomes (connection refused, timeout, TLS error, certificate) are visible in the results. |
| **Your IP appears in other people's logs** | Targets see connections from your server. Abuse complaints would come to you. |
| **DNS side channel** | Lookups come from your resolver, so an attacker running a DNS server learns your resolver's address and can see when lookups happen. |
| **Internal DNS names can be guessed** | If your resolver also answers internal names, the error for a name that resolves to a private address (`blocked_address`) differs from the one for a name that does not exist (`dns_error`). That lets a caller test whether internal hostnames exist. It reveals only existence, never the address. |
| **Hostile servers** | A remote server can present odd certificates, stall the handshake, or accept a connection and say nothing. |
| **Resource exhaustion** | Each inspection holds a worker thread until it finishes or times out. |

### SSRF and abuse protections that exist today

| Protection | How it works |
|---|---|
| Strict input | Only a bare, fully qualified domain name is accepted. URLs, ports, paths, credentials, single-label names and IP literals (including `0x7f.1`-style forms) are rejected before any lookup. |
| Port is a constant | Connections go to port **443** only. There is no port parameter anywhere in the API. |
| Every address must be public | DNS is resolved **once**. If *any* returned address is private, loopback, link-local, multicast, reserved, unspecified, carrier-grade NAT, documentation/benchmark space, or an IPv6 form that can embed an IPv4 address (mapped, 6to4, Teredo, NAT64), the whole request is refused. Mixed answers (one public, one internal) are refused too. |
| DNS rebinding | The TCP connection goes to the already-validated IP address, never to the hostname, so a second DNS answer cannot redirect it. SNI and certificate hostname checks still use the original name. |
| No application traffic | CertWatch performs a TLS handshake and reads the certificate. It sends no HTTP request, follows no redirects and reads no response body. |
| Re-validation on every check | Each Monitor check repeats validation and the address checks. A saved domain that later starts resolving to an internal address is refused on its next check. |
| Minimum TLS 1.2 | Older protocol versions are not negotiated. |
| Bounded work | DNS 3 s, TCP connect 5 s and handshake 5 s per address (at most 3 addresses), and a 15 s overall deadline; at most 8 inspections at once, shared by Inspector and Monitor. |
| Hostile certificates | A certificate that cannot be parsed produces a clean `tls_error` (and a recorded failed check in the Monitor), not a crash. |

**Defence in depth.** These checks live in the application. If you run CertWatch somewhere with sensitive internal
services, also restrict its **network egress**: for Docker on Linux, add host firewall rules in the `DOCKER-USER` chain
that drop traffic from the CertWatch containers to private ranges and the cloud metadata address, for example
`iptables -I DOCKER-USER -d 169.254.169.254 -j DROP`. On cloud hosts, enforce the metadata service's token requirement
(for example AWS IMDSv2). Inside Docker, names such as `backend` are rejected as single-label names, and any container
address they could resolve to is private and blocked.

### Are the rate limits and domain restrictions enough?

| Control | Setting | Assessment |
|---|---|---|
| Inspector and CertDiff rate limit | 10 requests / minute / client (shared) | Good for one user or a trusted team. |
| Monitor add and check rate limit | 20 requests / minute / client (separate budget) | Same. |
| Per-domain check cooldown | 10 s | Stops repeated manual checks hammering one host. Does not apply to the Inspector. |
| Concurrency cap | 8 inspections at once (global) | Protects the server, but is a shared resource (see below). |
| Monitored-domain cap | 100 total | Bounds database growth, but is global, not per user. |
| Domain and address validation | See above | **Sufficient to keep the server out of private networks.** It does *not* stop use against public hosts. |

**Verdict:** sufficient for local, single-user and trusted private deployments. **Not sufficient as the only protection
for a public deployment.** Specifically:

1. Limits are **per client address**, so an attacker with many addresses is not slowed down, and a spoofed address header
   defeats them if the backend is reachable directly.
2. Counters are **in memory and per process**: they reset on restart and are multiplied by the number of workers.
3. The **global concurrency cap can be exhausted** by a few clients, which makes everyone else see `503 busy`. That is an
   availability problem, not a data leak.
4. There is **no allow-list or deny-list of targets**, so public hosts can be probed (see the risk table).
5. The 100-domain cap and the Monitor API are shared by everyone who can reach the app.

These are inherent to an unauthenticated design, and tighter limits would not change that. That is why the guidance
above is to require authentication or network-level access control before exposing CertWatch, not to rely on the limits.

### Hardening checklist for a shared or internet-reachable deployment

- [ ] Authentication in front of **both** the UI and `/api/` (reverse proxy, VPN or private network).
- [ ] TLS on any network you do not control.
- [ ] Backend port 8000 not published; only the proxy can reach it.
- [ ] Egress from the CertWatch containers filtered (private ranges and cloud metadata address blocked).
- [ ] Proxy-level rate limiting (for example nginx `limit_req`) in addition to the built-in limits.
- [ ] Only one CertWatch instance, or an understanding that rate-limit counters are per process.
- [ ] The `certwatch-data` volume backed up if you rely on the monitoring history.
- [ ] Images and dependencies kept up to date (`pip-audit`, `npm audit`).

## Limitations

- **No authentication.** CertWatch must not be exposed publicly without access controls; see [Deployment and Security Considerations](#deployment-and-security-considerations). Docker publishes the UI on `127.0.0.1` only.
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
