"""M39 — profiles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loglens.profiles import (
    BUILTIN_PROFILES,
    Profile,
    ProfileStore,
    apply_profile,
)


class TestProfileDataclass:
    def test_roundtrip(self):
        p = Profile(name="x", description="d", query="level:error+", enrich=False)
        restored = Profile.from_dict(p.to_dict())
        assert restored.name == "x"
        assert restored.description == "d"
        assert restored.query == "level:error+"
        assert restored.enrich is False

    def test_defaults(self):
        p = Profile.from_dict({"name": "n"})
        assert p.stitch is True
        assert p.enrich is True
        assert p.query is None
        assert p.fields == {}

    def test_minimal_dict(self):
        assert Profile(name="n").to_dict() == {"name": "n"}


class TestBuiltins:
    def test_builtin_names(self):
        assert set(BUILTIN_PROFILES) == {"errors", "5xx", "tracebacks", "slow"}

    def test_errors_profile_query(self):
        assert "error" in (BUILTIN_PROFILES["errors"].query or "")


class TestProfileStore:
    def test_loads_builtins_without_file(self, tmp_path: Path):
        store = ProfileStore(directory=tmp_path)
        assert "errors" in store.load()

    def test_get_unknown_raises(self, tmp_path: Path):
        with pytest.raises(KeyError):
            ProfileStore(directory=tmp_path).get("ghost")

    def test_save_and_reload(self, tmp_path: Path):
        store = ProfileStore(directory=tmp_path)
        store.save(Profile(name="mine", query="status = 418"))
        loaded = store.get("mine")
        assert loaded.query == "status = 418"

    def test_user_overrides_builtin(self, tmp_path: Path):
        store = ProfileStore(directory=tmp_path)
        store.save(Profile(name="errors", query="custom"))
        assert store.get("errors").query == "custom"

    def test_save_twice_no_duplicate(self, tmp_path: Path):
        store = ProfileStore(directory=tmp_path)
        store.save(Profile(name="p", query="a"))
        store.save(Profile(name="p", query="b"))
        raw = json.loads((tmp_path / "profiles.json").read_text(encoding="utf-8"))
        names = [e["name"] for e in raw["profiles"]]
        assert names.count("p") == 1
        assert store.get("p").query == "b"

    def test_corrupt_file_falls_back_to_builtins(self, tmp_path: Path):
        (tmp_path / "profiles.json").write_text("{not json", encoding="utf-8")
        store = ProfileStore(directory=tmp_path)
        assert "errors" in store.load()


class TestApplyProfile:
    def test_overlay_sets_query(self):
        class Args:
            fmt = None
            query = None
            no_stitch = False
            no_enrich = False

        args = Args()
        apply_profile(args, BUILTIN_PROFILES["errors"])
        assert args.query == "level:error+"

    def test_existing_query_not_overwritten(self):
        class Args:
            fmt = None
            query = "keep me"
            no_stitch = False
            no_enrich = False

        args = Args()
        apply_profile(args, BUILTIN_PROFILES["errors"])
        assert args.query == "keep me"

    def test_no_enrich_flag(self):
        class Args:
            fmt = None
            query = None
            no_stitch = False
            no_enrich = False

        args = Args()
        apply_profile(args, BUILTIN_PROFILES["tracebacks"])
        assert args.no_enrich is True
