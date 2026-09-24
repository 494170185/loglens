"""M42c — offline IP classification (no network, no external database)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from loglens.extract import is_ipv4
from loglens.model import Record

_PRIVATE_PREFIXES = (
    ("10.", "private"),
    ("192.168.", "private"),
    ("127.", "loopback"),
    ("169.254.", "link-local"),
    ("172.16.", "private"),
    ("172.17.", "private"),
    ("172.18.", "private"),
    ("172.19.", "private"),
    ("172.2", "private"),
    ("172.30.", "private"),
    ("172.31.", "private"),
    ("0.", "reserved"),
)

_CGNAT_RE = re.compile(r"^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.")


@dataclass
class IpClass:
    address: str
    scope: str  # private | loopback | link-local | cgnat | public | invalid

    @property
    def is_public(self) -> bool:
        return self.scope == "public"


def classify_ip(address: str) -> IpClass:
    """Classify one IPv4 address without any network access."""
    if not is_ipv4(address):
        return IpClass(address=address, scope="invalid")
    if address.startswith("127."):
        return IpClass(address, "loopback")
    if address.startswith("169.254."):
        return IpClass(address, "link-local")
    if _CGNAT_RE.match(address):
        return IpClass(address, "cgnat")
    if address.startswith("10.") or address.startswith("192.168."):
        return IpClass(address, "private")
    if _in_172_range(address):
        return IpClass(address, "private")
    if address.startswith("0.") or address.startswith("255."):
        return IpClass(address, "reserved")
    return IpClass(address, "public")


def _in_172_range(address: str) -> bool:
    if not address.startswith("172."):
        return False
    try:
        second = int(address.split(".")[1])
    except (IndexError, ValueError):
        return False
    return 16 <= second <= 31


def ip_scope_counts(records: Iterable[Record], field: str = "client") -> dict[str, int]:
    """Tally requesters by IP scope (private/public/bot nets...)."""
    from loglens.aggregate import field_value

    counts: dict[str, int] = {}
    for rec in records:
        raw = field_value(rec, field)
        if not isinstance(raw, str):
            continue
        scope = classify_ip(raw).scope
        counts[scope] = counts.get(scope, 0) + 1
    return counts


def public_clients(records: Iterable[Record], field: str = "client") -> list[str]:
    """Distinct public addresses in first-seen order."""
    from loglens.aggregate import field_value

    seen: set[str] = set()
    out: list[str] = []
    for rec in records:
        raw = field_value(rec, field)
        if not isinstance(raw, str):
            continue
        info = classify_ip(raw)
        if info.is_public and raw not in seen:
            seen.add(raw)
            out.append(raw)
    return out
