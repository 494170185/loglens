"""M39 — named profiles: reusable option bundles for common scans."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PROFILE_DIR = Path.home() / ".config" / "loglens"


@dataclass
class Profile:
    """A named bundle of collector/filter defaults."""

    name: str
    description: str = ""
    format_hint: str | None = None
    stitch: bool = True
    enrich: bool = True
    query: str | None = None
    fields: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {"name": self.name}
        if self.description:
            out["description"] = self.description
        if self.format_hint:
            out["format"] = self.format_hint
        if not self.stitch:
            out["stitch"] = False
        if not self.enrich:
            out["enrich"] = False
        if self.query:
            out["query"] = self.query
        if self.fields:
            out["fields"] = self.fields
        return out

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Profile:
        return cls(
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            format_hint=data.get("format"),  # type: ignore[arg-type]
            stitch=bool(data.get("stitch", True)),
            enrich=bool(data.get("enrich", True)),
            query=data.get("query"),  # type: ignore[arg-type]
            fields=dict(data.get("fields", {})),  # type: ignore[arg-type]
        )


BUILTIN_PROFILES: dict[str, Profile] = {
    p.name: p
    for p in [
        Profile(
            name="errors",
            description="errors and warnings only",
            query="level:error+",
        ),
        Profile(
            name="5xx",
            description="server errors from access logs",
            query="status >= 500",
            format_hint="access",
        ),
        Profile(
            name="tracebacks",
            description="raw records with multiline stitching, no extraction",
            enrich=False,
        ),
        Profile(
            name="slow",
            description="requests slower than a second",
            query="duration_ms > 1000",
        ),
    ]
}


class ProfileStore:
    """Load and save profiles: builtins first, user files override."""

    def __init__(self, directory: Path | None = None):
        self.directory = Path(directory) if directory else DEFAULT_PROFILE_DIR

    def load(self) -> dict[str, Profile]:
        merged: dict[str, Profile] = dict(BUILTIN_PROFILES)
        user_file = self.directory / "profiles.json"
        if user_file.is_file():
            try:
                payload = json.loads(user_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return merged
            for entry in payload.get("profiles", []):
                if isinstance(entry, dict) and entry.get("name"):
                    profile = Profile.from_dict(entry)
                    merged[profile.name] = profile
        return merged

    def get(self, name: str) -> Profile:
        profiles = self.load()
        if name not in profiles:
            raise KeyError(f"unknown profile {name!r}")
        return profiles[name]

    def save(self, profile: Profile) -> Path:
        """Persist a profile to the user store (creates the directory)."""
        self.directory.mkdir(parents=True, exist_ok=True)
        user_file = self.directory / "profiles.json"
        existing: dict[str, list[dict]] = {"profiles": []}
        if user_file.is_file():
            try:
                existing = json.loads(user_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {"profiles": []}
        entries = existing.get("profiles", [])
        entries = [e for e in entries if e.get("name") != profile.name]
        entries.append(profile.to_dict())
        existing["profiles"] = entries
        user_file.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return user_file


def apply_profile(args, profile: Profile) -> None:
    """Overlay a profile onto parsed CLI args (mutates args)."""
    if profile.format_hint and getattr(args, "fmt", None) is None:
        args.fmt = profile.format_hint
    if not profile.stitch:
        args.no_stitch = True
    if not profile.enrich:
        args.no_enrich = True
    if profile.query and not getattr(args, "query", None):
        args.query = profile.query
