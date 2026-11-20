import pytest

from app.services.hostname import hostname_matches


@pytest.mark.parametrize(
    "host,names,ok",
    [
        ("example.com", ["example.com"], True),
        ("EXAMPLE.com", ["example.COM"], True),
        ("www.example.com", ["*.example.com"], True),
        ("example.com", ["*.example.com"], False),
        ("a.b.example.com", ["*.example.com"], False),
        ("evil.com", ["example.com"], False),
        ("foo.com", ["*.com"], False),
        ("www.example.com", ["www.*.com"], False),
        ("www.example.com", ["w*.example.com"], False),
        ("example.com", [], False),
    ],
)
def test_match(host, names, ok):
    assert hostname_matches(host, names) is ok
