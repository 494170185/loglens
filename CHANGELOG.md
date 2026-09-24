# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Milestone history

Development proceeds in numbered milestones; each one is a meaningful,
self-contained step forward and later milestones build on earlier ones.

- **M1** — Record model: raw line, message, timestamp, level, structured
  fields, source and line number; immutable copies via dataclasses.replace.
- **M2** — Line reader with UTF-8/latin-1 fallback, CRLF handling, and
  1-based numbering.
- **M3** — Severity normalization: aliases (warn/warning/err/fatal...),
  syslog 0-7 and Python 10-50 numbers, word scan for free text.
- **M4** — Multi-dialect timestamp parser: ISO 8601 (offsets, fractional
  seconds), nginx/apache formats, RFC 3164 syslog with pinned year, epoch
  seconds/millis, slash dates, log4j comma-millis. UTC normalization,
  bucket rounding, gap arithmetic.
- **M5** — Combined/common access-log parser with status classes.
- **M6** — JSON Lines parser: key aliases (`ts`/`@timestamp`/`severity`...),
  one-level flattening, value rendering for filters.
- **M7** — logfmt parser: quoting, escapes, typed coercion.
- **M8** — Syslog RFC 3164/5424: priority decoding, facility names.
- **M9** — Format auto-detection by majority vote over a sample window,
  plus the plain `timestamp [level] message` parser.
- **M10** — Multiline stitching: Python/Java/Go stack vocabulary folded
  into the parent record, streaming variant included.
- **M11** — Free-text field extraction: IPs, UUIDs, URLs, durations (ms
  normalized), paths, loose kv pairs.
- **M12** — Collection pipeline (detect → parse → stitch → enrich) with
  per-run stats.
- **M13** — Filter lexer: strings with escapes, numbers, operators,
  keyword operators, malformed-operator guards.
- **M14** — Recursive descent parser and AST with lazy evaluation; the
  expression language ships.
- **M15** — Built-in predicates (LevelAtLeast, HasField, FromSource,
  RegexFilter), record-to-context bridge, `level:warn+` shorthands.
- **M16** — Group-by aggregation with composite keys and sorting by
  count/avg/first.
- **M17** — Descriptive metrics: nearest-rank percentiles (p50/p95/p99),
  stdev, status breakdown with error rate.
- **M18** — Top-N rankings by count/avg/sum/max.
- **M19** — ASCII histograms and latency profiles.
- **M20** — Time bucketing with zero-filled gaps, rate and error-rate
  series, window slicing.
- **M21** — Request classification: path taxonomy (api/static/auth/...),
  verb groups, MIME mapping.
- **M22** — Rate-shift detection (adjacent-bucket spikes and drops) and
  single-bucket spikes.
- **M23** — Gzip-transparent reading by magic bytes.
- **M24** — Multi-file merging by timestamp with stable tie-breaking.
- **M25** — URL breakdown: query params, route shapes, normalized paths.
- **M26** — User-agent parsing: family, version, OS, device, bot flag.
- **M27** — Watch mode: tail-follow with truncation/rotation recovery.
- **M28** — Repeat-burst detection with message normalization.
- **M29** — Z-score anomaly detection on numeric fields.
- **M30** — Silence gap detection and freshness reporting.
- **M31** — Sessionization by client with idle-timeout splitting.
- **M32** — Output writers: text, JSON lines, JSON array, CSV.
- **M33** — ANSI palette with NO_COLOR/FORCE_COLOR/TERM handling.
- **M34** — Terminal tables with CJK-aware display width alignment.
- **M35** — Markdown report builder and one-shot summary report.
- **M36** — CLI entry point, `cat` command, input resolution (files, globs,
  directories, stdin).
- **M37** — Commands: stats, filter, grep, top, hist, timeline, report.
- **M38** — Commands: bursts, anomalies, silences, sessions, watch,
  classify; access-log records now carry parsed timestamps.
- **M39** — Named profiles: builtins plus user overrides in
  `~/.config/loglens/profiles.json`.
- **M40** — Lazy streaming pipeline with composable stages (filter, limit,
  offset, map, dedup, min-level, sample, stats).
- **M41** — `doctor` self-check: python version, parsers, filter language,
  tables, profiles, module imports.
- **M42** — Production hardening batch:
  reservoir/distinct samplers and sliding windows; cross-stream
  correlation, field joins, co-occurrence; stream diffing; offline IP
  classification (private/loopback/CGNAT/link-local); declarative rule
  packs; format consistency audit; byte-offset resume store; sparklines;
  field coverage inventory; SLO evaluation with error budgets; labeled
  time-window index; match highlighting; adaptive column widths;
  detector threshold tuning; packaging (pyproject, entry point,
  `python -m loglens`); benchmark script.

### Added
- Everything above; initial public repository state.

[Unreleased]: https://example.com/loglens/compare/v0.0.1...HEAD
