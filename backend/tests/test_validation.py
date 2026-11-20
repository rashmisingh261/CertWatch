import pytest

from app.core.errors import InvalidDomainError
from app.core.validation import validate_domain


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("example.com", "example.com"),
        ("  Example.COM. ", "example.com"),
        ("sub.domain.example.co.uk", "sub.domain.example.co.uk"),
        ("bücher.de", "xn--bcher-kva.de"),
        ("a-b.example.com", "a-b.example.com"),
    ],
)
def test_valid(raw, expected):
    assert validate_domain(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "", "   ", "localhost", "https://example.com", "example.com/path",
        "example.com:8443", "user@example.com", "example.com?x=1", "exa mple.com",
        "127.0.0.1", "10.0.0.1", "0x7f.1", "[::1]", "::1", "-bad.example.com",
        "bad-.example.com", "a..b.com", "a" * 64 + ".com", ("a." * 130) + "com",
        "exa_mple.com", "example.com\n.evil.com", "1.2.3.4.5",
    ],
)
def test_invalid(raw):
    with pytest.raises(InvalidDomainError):
        validate_domain(raw)
