"""M26 — user-agent parsing: browser, bot, OS, version."""

from __future__ import annotations

import re


class UserAgentInfo:
    """Parsed user-agent summary."""

    def __init__(self, family: str, version: str, os_name: str, device: str, is_bot: bool):
        self.family = family
        self.version = version
        self.os_name = os_name
        self.device = device
        self.is_bot = is_bot

    def as_dict(self) -> dict[str, object]:
        return {
            "ua_family": self.family,
            "ua_version": self.version,
            "ua_os": self.os_name,
            "ua_device": self.device,
            "ua_bot": self.is_bot,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"UserAgentInfo({self.family} {self.version}, {self.os_name})"


_BOTS = re.compile(
    r"bot|crawler|spider|slurp|curl|wget|python-requests|okhttp|"
    r"monitor|pingdom|uptimerobot|headlesschrome|phantomjs|scrapy|axios",
    re.I,
)

_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Edge", re.compile(r"Edge/(\d+)")),
    ("Opera", re.compile(r"OPR/(\d+)|Opera[ /](\d+)")),
    ("Firefox", re.compile(r"Firefox/(\d+)")),
    ("Safari", re.compile(r"Version/(\d+).*Safari")),
    ("Chrome", re.compile(r"Chrome/(\d+)")),
    ("Safari", re.compile(r"Safari")),
    ("IE", re.compile(r"MSIE (\d+)|Trident/.*rv:(\d+)")),
    ("curl", re.compile(r"curl/([\d.]+)")),
    ("Wget", re.compile(r"Wget/([\d.]+)")),
    ("Python", re.compile(r"[Pp]ython-[Rr]equests/([\d.]+)|[Pp]ython-[Uu]rllib/([\d.]+)")),
    ("Java", re.compile(r"Java/([\d._]+)")),
    ("OkHttp", re.compile(r"okhttp/([\d.]+)")),
)

_OS_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("iOS", re.compile(r"iPhone|iPad")),
    ("Android", re.compile(r"Android")),
    ("Windows", re.compile(r"Windows NT")),
    ("macOS", re.compile(r"Mac OS X|Macintosh")),
    ("ChromeOS", re.compile(r"CrOS")),
    ("Linux", re.compile(r"Linux|X11")),
)


def parse_user_agent(agent: str | None) -> UserAgentInfo:
    """Parse a user-agent string into family/version/OS/device/bot."""
    if not agent:
        return UserAgentInfo("unknown", "", "unknown", "other", False)
    text = agent

    family, version = "unknown", ""
    for name, pattern in _FAMILIES:
        m = pattern.search(text)
        if m:
            family = name
            version = next((g for g in m.groups() if g), "")
            break

    os_name = "unknown"
    for name, pattern in _OS_RULES:
        if pattern.search(text):
            os_name = name
            break

    if re.search(r"iPhone|Android.*Mobile", text):
        device = "phone"
    elif re.search(r"iPad|Tablet", text):
        device = "tablet"
    else:
        device = "desktop" if os_name != "unknown" else "other"

    is_bot = bool(_BOTS.search(text)) or family in ("curl", "Wget", "Python", "OkHttp")
    return UserAgentInfo(family, version, os_name, device, is_bot)


def enrich_fields_with_ua(fields: dict[str, object], key: str = "agent") -> dict[str, object]:
    """Add ua_* fields to a record mapping (no mutation)."""
    raw = fields.get(key)
    if not isinstance(raw, str) or not raw:
        return fields
    merged = dict(fields)
    merged.update(parse_user_agent(raw).as_dict())
    return merged
