# loglens

A command-line toolkit for slicing through server logs: parse common formats
(nginx/apache access & error logs, JSON lines, syslog, logfmt), filter with a
small expression language, aggregate, and surface anomalies — all from the
terminal, with zero runtime dependencies beyond the Python standard library.

Status: early development. See `CHANGELOG.md` for the milestone history.

## Milestones

Development is organized in numbered milestones; each one is a meaningful,
self-contained step forward and later milestones build on earlier ones.

1. Record model and plain-text parsing
