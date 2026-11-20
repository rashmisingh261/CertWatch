"""Strict domain-name validation.

We accept only a bare hostname. URLs, ports, paths, credentials, IP literals and
single-label names (e.g. ``localhost``) are rejected up front.
"""
from __future__ import annotations

import re

from app.core.errors import InvalidDomainError

_LABEL_RE = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")


def validate_domain(raw: str) -> str:
    """Return the normalised (lower-case, punycode/ASCII) domain or raise InvalidDomainError."""
    if not isinstance(raw, str):
        raise InvalidDomainError("Domain must be a string.")
    value = raw.strip().rstrip(".")
    if not value:
        raise InvalidDomainError("Please enter a domain name.")
    if len(value) > 253:
        raise InvalidDomainError("Domain name is too long.")
    if "://" in value or any(c in value for c in "/\\?#@:[]% \t\r\n"):
        raise InvalidDomainError(
            "Enter a bare domain name such as example.com (no URL, port, path or credentials)."
        )

    try:
        ascii_name = value.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise InvalidDomainError("Domain contains invalid characters.") from None
    if len(ascii_name) > 253:
        raise InvalidDomainError("Domain name is too long.")

    labels = ascii_name.split(".")
    if len(labels) < 2:
        raise InvalidDomainError("Enter a fully qualified domain name such as example.com.")
    if not all(_LABEL_RE.match(label) for label in labels):
        raise InvalidDomainError("Domain contains invalid characters or malformed labels.")
    # A numeric TLD means this is an IP literal (or an obfuscated one such as 0x7f.1).
    if labels[-1].isdigit() or labels[-1].startswith("0x"):
        raise InvalidDomainError("IP addresses are not accepted; enter a domain name.")
    return ascii_name
