# Demo walkthrough and screenshot checklist

Everything here uses **generated certificates and documentation-only domains** (`example.com`, `example.org`,
`example.net`). No real hosts, private keys or secrets are involved and no internet access is needed.

## Start the demo

```bash
# Terminal 1 - backend with the network layer replaced by generated certificates
backend/.venv/bin/python scripts/demo.py serve

# Terminal 2 - the UI
cd frontend && npm run dev          # open http://localhost:5173
```

The demo uses a temporary database (your real one is never touched) and these demo domains:

| Domain | What it demonstrates |
|---|---|
| `example.com` | Valid, trusted certificate (SANs `example.com`, `www.example.com`) |
| `expiring.example.com` | Trusted, expires in 12 days → *Expiring soon* |
| `expired.example.com` | Expired certificate |
| `mismatch.example.org` | Trusted chain but the certificate is for a different hostname |
| `selfsigned.example.net` | Not trusted (self-signed) but still displayed |
| `down.example.com` | Connection refused → *Check failed* |
| anything else | DNS failure |

Generate two sample PEM files for the CertDiff step (public certificates only; the keys are discarded):

```bash
backend/.venv/bin/python scripts/demo.py certs ./demo-certs
```

## Walkthrough (about three minutes)

### 1. Inspect a domain

1. **Inspector** tab → enter `example.com` → **Inspect**.
2. Point out the green *valid and trusted* banner. **Trusted chain**, **Hostname matches** and **Within validity period**
   are three separate checks.
3. Try `selfsigned.example.net`: the certificate is still shown, but the banner says **NOT trusted** and gives the reason.
   Inspecting a certificate and trusting it are different things.
4. Try `localhost` or `http://example.com`: a clear validation error, and no connection is attempted.

### 2. Compare two certificates

1. **CertDiff** tab → choose `demo-certs/certificate-a.pem` as A and `certificate-b.pem` as B → **Compare Certificates**.
2. The table marks the issuer, serial, expiry and fingerprints as **Modified**; unchanged fields stay **Unchanged**.
3. In *Subject Alternative Names*, `www.example.com` is **removed** (A only) and `api.example.com` is **added** (B only).
4. Click **Details** on *Certificate fingerprint* to see why a different fingerprint is not, by itself, a problem.
5. Tick **Show differences only**, then **Export JSON**.
6. Try uploading something that is not a certificate (any text file): a clear error, no crash.

### 3. Add a domain to monitoring

1. **Monitor** tab → add `example.com`. It appears as **Healthy** with issuer, expiry and days remaining.
2. Add `expiring.example.com` (→ *Expiring soon*), `expired.example.com` (→ *Expired*) and `down.example.com`
   (→ *Check failed*; it is saved so you can see how failures are shown).
3. Click **History** on `example.com`: one observation.

### 4. Detect a certificate change

1. In a third terminal, simulate the site renewing its certificate:
   ```bash
   backend/.venv/bin/python scripts/demo.py rotate example.com
   ```
2. Back in the UI, click **Check now** on `example.com`. The status becomes **Changed**.
3. Open **History**: the new entry shows the new fingerprint, exactly what differs (serial, validity, public key, SANs
   added/removed) and a neutral hint. The **previous observation is still there**, unmodified.
4. Click **Check now** again: the status returns to **Healthy**, and the change stays in the history.

## Screenshot checklist

Capture at roughly 1280 px wide (and optionally one at phone width). Save PNGs in `docs/screenshots/` using these names
(see also [screenshots/README.md](screenshots/README.md)), then uncomment the images in the main README.

- [ ] `dashboard.png`: Inspector tab, empty state (main dashboard)
- [ ] `inspector.png`: results for `example.com` (green banner, expiry, SANs, fingerprint)
- [ ] `inspector-untrusted.png`: results for `selfsigned.example.net` (trust shown separately from retrieval)
- [ ] `certdiff.png`: comparison of the two sample certificates, SAN chips visible
- [ ] `monitor.png`: Monitor tab with the demo domains in different states
- [ ] `monitor-history.png`: history after the rotation, showing the change box

Before publishing, check that no screenshot contains real domains, personal data, browser bookmarks or tabs, local paths
or tokens.
