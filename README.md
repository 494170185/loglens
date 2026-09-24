# loglens

A command-line toolkit for slicing through server logs: parse common formats
(nginx/apache access & error logs, JSON lines, syslog, logfmt, plain app
logs), filter with a small expression language, aggregate, and surface
anomalies — all from the terminal, with zero runtime dependencies beyond
the Python standard library.

## Install

```
pip install .          # or run from source: python -m loglens
```

Requires Python 3.12+. There are no runtime dependencies; dev tooling
(pytest, ruff) is optional (`pip install -e .[dev]`).

## Quick tour

```
# what is in this file?
loglens stats access.log

# keep errors only, print as JSON lines
loglens cat app.log -q "level:error+" -f jsonl

# which clients hit us the most?
loglens top access.log client -n 20

# latency distribution
loglens hist access.log bytes --bins 30

# requests per minute with 5xx fraction
loglens timeline access.log --bucket 5m --errors

# find the repeated-message bursts and statistical outliers
loglens bursts app.log
loglens anomalies app.log duration_ms --min-z 3.5

# quiet gaps in the stream
loglens silences app.log --min-seconds 600

# per-client sessions and request categories
loglens sessions access.log --timeout-minutes 15
loglens classify access.log

# markdown report for the on-call handover
loglens report app.log -o incident.md

# tail a growing file with a live filter
loglens watch /var/log/app.log -q "status >= 500"

# environment self-check
loglens doctor
```

## The filter language

```
level:error+ and status >= 500
path ~= ^/api/ and not host = canary
msg contains timeout
client in 10.0.0.1
```

- `and / or / not` with parentheses, standard precedence.
- Comparisons: `=`, `!=`, `<`, `<=`, `>`, `>=`, `contains`, `~= (regex)`, `in`.
- A bare word matches anywhere in the message or raw line.
- `level:warn+` expands to "warning or worse".
- Missing fields satisfy `!=` and nothing else (no false positives on
  absent data).

## Supported formats (auto-detected)

| Format  | Example |
|---------|---------|
| access  | `1.2.3.4 - - [19/Sep/2026:10:07:21 +0000] "GET / HTTP/1.1" 200 512` |
| json    | `{"ts": "...", "level": "error", "msg": "boom"}` |
| logfmt  | `level=info msg=starting port=8080` |
| syslog  | `Sep 19 10:07:21 host app[123]: msg` (RFC 3164 and 5424) |
| plain   | `2026-09-19 10:07:21 INFO service starting` |
| raw     | anything else, kept verbatim |

Detection samples the first lines of each file and routes every line
through the winning parser; parse failures fall back to raw records, so a
mixed file never crashes a scan. Gzip files are detected by magic bytes
(`.gz` extension not required). Files can also be piped through stdin.

Multiline stack traces (Python tracebacks, Java `Caused by:`, Go panics)
are stitched into their parent record, so an error plus its traceback is
one logical event.

## What it extracts

Free-text messages are enriched with:

- IPv4 addresses (octet-validated) under `ip` / `ips`
- UUIDs, URLs, absolute paths
- durations normalized to milliseconds (`timeout after 5s` → `duration_ms: 5000`)
- loose `key=value` / `key: value` pairs

Access-log records additionally resolve route shapes
(`/api/users/42` → `/api/users/:id`), query parameters, user-agent
families (browser/bot, OS, device class) and request categories
(api/static/auth/health/admin/webhook).

## Library use

Everything behind the CLI is importable:

```python
from loglens.collect import Collector
from loglens.filters.builtin import compile_query, record_context
from loglens.pipeline import Pipeline, stage_filter, stage_min_level

records = Collector().collect_file("app.log")
flt = compile_query("level:error+ and status >= 500")
errors = [r for r in records if flt.matches(record_context(r))]

# or build a lazy pipeline over a stream
stats = ...
pipeline = Pipeline().then(stage_min_level("warning")).then(stage_filter(...))
for rec in pipeline.iter(iter(records)):
    ...
```

Notable modules: `loglens.timebuckets` (gap-filled time series),
`loglens.shifts` (rate-shift detection), `loglens.sessions` (sessionization),
`loglens.slo` (availability + latency SLOs and error budgets),
`loglens.correlate` (join two log streams), `loglens.windows` (labeled time
windows), `loglens.tuning` (data-driven detector thresholds).

## Profiles

Reusable option bundles live in `~/.config/loglens/profiles.json` and
override the built-ins (`errors`, `5xx`, `tracebacks`, `slow`). See
`loglens.profiles` for the file format.

## Development

```
pip install -e .[dev]
pytest                  # 777 tests
ruff check .            # lint
python scripts/bench.py # throughput benchmark
```

The project is organized in numbered milestones (M1-M42+); each milestone
is one meaningful step and later ones build on earlier ones. See
`CHANGELOG.md`.

## License

MIT.
