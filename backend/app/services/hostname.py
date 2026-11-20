"""Certificate hostname matching (RFC 6125 style, SAN only).

Wildcards are honoured only as the entire left-most label and never match across dots
or bare public-suffix-style names (``*.com``).
"""
from __future__ import annotations

from typing import Iterable


def _match_one(pattern: str, host: str) -> bool:
    pattern, host = pattern.lower().rstrip("."), host.lower().rstrip(".")
    if "*" not in pattern:
        return pattern == host
    p_labels, h_labels = pattern.split("."), host.split(".")
    if len(p_labels) < 3 or p_labels[0] != "*" or "*" in "".join(p_labels[1:]):
        return False  # only '*.example.tld' form; at least 3 labels
    return len(p_labels) == len(h_labels) and p_labels[1:] == h_labels[1:]


def hostname_matches(host: str, dns_names: Iterable[str]) -> bool:
    return any(_match_one(n, host) for n in dns_names)
