#!/usr/bin/env python3
"""CertWatch demo helper: for documentation and screenshots only (not part of the app).

Runs the real CertWatch app with its network layer replaced by *generated* certificates for
documentation-only domains (example.com, example.org, example.net). No internet access, real
domains, private keys or secrets are involved, and it never touches your real database.

    python scripts/demo.py serve              # start the demo backend on 127.0.0.1:8000
    python scripts/demo.py rotate example.com # simulate that site renewing its certificate
    python scripts/demo.py certs ./demo-certs # write two sample PEM certificates for CertDiff

Run it with the backend virtualenv, e.g.  backend/.venv/bin/python scripts/demo.py serve
"""
from __future__ import annotations

import argparse
import datetime as dt
import socket
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from cryptography.x509.oid import NameOID  # noqa: E402

PUBLIC_IP = "93.184.216.34"  # never connected to: the demo replaces the network layer
ISSUER = "CertWatch Demo CA"


def make_cert_pem(
    domain: str,
    *,
    issuer: str = ISSUER,
    sans: Optional[List[str]] = None,
    days: float = 80,
    started_days_ago: float = 10,
    serial: Optional[int] = None,
    cn: Optional[str] = None,
) -> bytes:
    """A throwaway self-signed certificate (the private key is discarded, never written)."""
    key = ec.generate_private_key(ec.SECP256R1())
    now = dt.datetime.now(dt.timezone.utc)
    names = [domain] if sans is None else sans
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn or domain)]))
        .issuer_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, issuer)]))
        .public_key(key.public_key())
        .serial_number(serial or x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=started_days_ago))
        .not_valid_after(now + dt.timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in names]), critical=False)
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM)


def _handshake(pem: bytes, verify_error: Optional[str] = None):
    from app.services.inspector import _Handshake

    der = x509.load_pem_x509_certificate(pem).public_bytes(serialization.Encoding.DER)
    return _Handshake(der, "TLSv1.3", "TLS_AES_256_GCM_SHA384", verify_error, 18 if verify_error else None)


# Each demo site: a function returning the current handshake (or raising a connection error).
SITES: Dict[str, Callable[[], object]] = {}
_current: Dict[str, object] = {}
_rotations: Dict[str, int] = {}


def _reset_sites() -> None:
    _current.clear()
    _rotations.clear()
    _current["example.com"] = _handshake(make_cert_pem("example.com", sans=["example.com", "www.example.com"]))
    _current["expiring.example.com"] = _handshake(make_cert_pem("expiring.example.com", days=12))
    _current["expired.example.com"] = _handshake(
        make_cert_pem("expired.example.com", days=-5, started_days_ago=90), "certificate has expired"
    )
    _current["mismatch.example.org"] = _handshake(
        make_cert_pem("mismatch.example.org", sans=["other.example.net"], cn="other.example.net")
    )
    _current["selfsigned.example.net"] = _handshake(
        make_cert_pem("selfsigned.example.net", issuer="selfsigned.example.net"), "self-signed certificate"
    )
    _current["down.example.com"] = ConnectionRefusedError()


def rotate(domain: str) -> None:
    """Simulate the site renewing: new key, new serial, longer validity, SANs changed."""
    if domain not in _current or isinstance(_current[domain], BaseException):
        raise KeyError(f"'{domain}' is not a demo site that serves a certificate")
    n = _rotations[domain] = _rotations.get(domain, 0) + 1
    _current[domain] = _handshake(
        make_cert_pem(domain, sans=[domain, f"api{n}.{domain}"], days=90, started_days_ago=0)
    )


def build_demo_app(db_path: Optional[str] = None):
    """Return the real FastAPI app with DNS/TLS mocked and an isolated demo database."""
    from app.core import config, network_guard
    from app.main import app
    from app.services import inspector

    config.DB_PATH = db_path or str(Path(tempfile.mkdtemp(prefix="certwatch-demo-")) / "demo.db")
    config.MONITOR_CHECK_COOLDOWN_SECONDS = 0  # let the walkthrough re-check immediately
    _reset_sites()

    def fake_getaddrinfo(host):
        if host not in _current:
            raise socket.gaierror(8, "demo: unknown host")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 443))]

    def fake_fetch(_addr, host):
        site = _current[host]
        if isinstance(site, BaseException):
            raise site
        return site

    network_guard._getaddrinfo = fake_getaddrinfo
    inspector._fetch = fake_fetch
    return app


def cmd_serve(args) -> None:
    import uvicorn

    app = build_demo_app()

    @app.post("/demo/rotate/{domain}", include_in_schema=False)
    def demo_rotate(domain: str):
        try:
            rotate(domain)
        except KeyError as exc:
            return {"ok": False, "error": str(exc)}
        return {"ok": True, "message": f"{domain} now serves a renewed certificate"}

    print("CertWatch DEMO: generated certificates only, no real network access, temporary database.")
    print("Demo domains:", ", ".join(sorted(_current)))
    print(f"Backend on http://{args.host}:{args.port}  (run `npm run dev` in frontend/ for the UI)")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def cmd_rotate(args) -> None:
    url = f"http://{args.host}:{args.port}/demo/rotate/{args.domain}"
    with urllib.request.urlopen(urllib.request.Request(url, method="POST"), timeout=5) as r:  # noqa: S310
        print(r.read().decode())


def cmd_certs(args) -> None:
    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    a = make_cert_pem("example.com", sans=["example.com", "www.example.com"], days=30, serial=1001)
    b = make_cert_pem("example.com", sans=["example.com", "api.example.com"], days=90, serial=1002,
                      issuer="CertWatch Demo CA 2")
    (out / "certificate-a.pem").write_bytes(a)
    (out / "certificate-b.pem").write_bytes(b)
    print(f"Wrote {out / 'certificate-a.pem'} and {out / 'certificate-b.pem'} (public certificates only).")


def main(argv: Optional[List[str]] = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("serve", help="start the demo backend")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)
    r = sub.add_parser("rotate", help="simulate a certificate renewal on a running demo")
    r.add_argument("domain")
    r.add_argument("--host", default="127.0.0.1")
    r.add_argument("--port", type=int, default=8000)
    r.set_defaults(func=cmd_rotate)
    c = sub.add_parser("certs", help="write two sample PEM certificates for the CertDiff demo")
    c.add_argument("outdir")
    c.set_defaults(func=cmd_certs)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
