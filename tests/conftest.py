"""Shared pytest fixtures: sample log lines reused across parser tests."""

from __future__ import annotations

import pytest

from loglens.model import Record


@pytest.fixture()
def nginx_line():
    return (
        '172.17.0.1 - - [19/Sep/2026:10:07:21 +0000] "GET /api/health HTTP/1.1" '
        '200 12 "-" "curl/8.5.0"'
    )


@pytest.fixture()
def plain_record():
    return Record(raw="hello world", message="hello world")
