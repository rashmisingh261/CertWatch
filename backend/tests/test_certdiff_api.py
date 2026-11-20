import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.core.rate_limit import limiter
from app.main import app
from tests.certgen import make_pem, private_key_pem

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset():
    limiter.reset()


def post(a, b, name_a="a.pem", name_b="b.pem"):
    return client.post(
        "/api/certdiff",
        files={
            "certificate_a": (name_a, a, "application/x-pem-file"),
            "certificate_b": (name_b, b, "application/x-pem-file"),
        },
    )


def test_success_and_response_shape():
    r = post(make_pem(sans=["example.com", "www.example.com"]), make_pem(sans=["example.com", "api.example.com"]))
    assert r.status_code == 200
    j = r.json()
    assert set(j) == {"compared_at", "certificate_a", "certificate_b", "summary", "fields"}
    assert j["certificate_a"]["filename"] == "a.pem"
    san = next(f for f in j["fields"] if f["key"] == "sans")
    assert san["removed"] == ["DNS:www.example.com"] and san["added"] == ["DNS:api.example.com"]
    assert sum(j["summary"].values()) == len(j["fields"]) == 14


def test_response_does_not_echo_file_contents():
    pem = make_pem()
    assert b"BEGIN CERTIFICATE" not in post(pem, pem).content


@pytest.mark.parametrize(
    "a,b,code,status,text",
    [
        (b"", make_pem(), "invalid_certificate", 422, "Certificate A"),
        (make_pem(), b"", "invalid_certificate", 422, "Certificate B"),
        (b"not a cert", make_pem(), "invalid_certificate", 422, "Certificate A"),
        (make_pem(), private_key_pem(), "invalid_certificate", 422, "private key"),
    ],
)
def test_bad_uploads(a, b, code, status, text):
    r = post(a, b)
    assert r.status_code == status
    assert r.json()["error"]["code"] == code and text in r.json()["error"]["message"]


def test_both_empty():
    r = post(b"", b"")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_certificate"


def test_oversized_file_rejected():
    big = b"A" * (config.MAX_UPLOAD_BYTES + 10)
    r = post(big, make_pem())
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_oversized_total_body_rejected_by_middleware():
    big = b"A" * (config.MAX_REQUEST_BYTES + 10)
    r = post(big, big)
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_chunked_oversize_body_without_content_length():
    """A well-formed multipart stream with no Content-Length must still hit the byte cap."""
    def gen():
        yield (b'--zz\r\nContent-Disposition: form-data; name="certificate_a"; '
               b'filename="a.pem"\r\n\r\n')
        for _ in range(40):
            yield b"x" * 100_000
        yield b"\r\n--zz--\r\n"
    r = client.post(
        "/api/certdiff", content=gen(), headers={"content-type": "multipart/form-data; boundary=zz"}
    )
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"


def test_missing_file_field():
    r = client.post("/api/certdiff", files={"certificate_a": ("a.pem", make_pem())})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    assert "certificate_b" in r.json()["error"]["message"]


def test_extension_not_trusted():
    # A valid certificate named .txt is accepted; a .pem containing junk is rejected.
    assert post(make_pem(), make_pem(), "x.txt", "y.jpg").status_code == 200
    assert post(b"junk", make_pem(), "x.pem", "y.pem").status_code == 422


def test_rate_limited():
    for _ in range(config.RATE_LIMIT_REQUESTS):
        post(b"", b"")
    assert post(b"", b"").status_code == 429


def test_phase1_endpoints_still_work():
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.post("/api/inspect", json={"domain": "localhost"}).status_code == 422
