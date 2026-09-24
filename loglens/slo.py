"""M42f — SLO evaluation from access-log records."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass
class SloResult:
    """Availability and latency compliance over a window."""

    total_requests: int
    good_responses: int
    availability: float  # 0..1
    fast_enough: int  # requests under the latency objective
    latency_compliance: float  # 0..1

    @property
    def ok(self) -> bool:
        return self.availability >= 0.99 and self.latency_compliance >= 0.95


def evaluate_slo(
    records: Iterable,
    latency_field: str = "dur",
    latency_budget_ms: float = 1000.0,
) -> SloResult:
    """Compute availability (non-5xx) and latency SLOs.

    Records lacking a status do not count toward availability; records
    lacking the latency field do not count toward latency compliance.
    """
    total = 0
    good = 0
    timed = 0
    fast = 0
    for rec in records:
        status = rec.get("status")
        if status is not None:
            try:
                code = int(status)
            except (TypeError, ValueError):
                code = -1
            total += 1
            if code < 500:
                good += 1
        value = rec.get(latency_field)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            timed += 1
            if float(value) <= latency_budget_ms:
                fast += 1
    availability = good / total if total else 1.0
    latency = fast / timed if timed else 1.0
    return SloResult(
        total_requests=total,
        good_responses=good,
        availability=availability,
        fast_enough=fast,
        latency_compliance=latency,
    )


def error_budget(
    records: Iterable,
    target_availability: float = 0.99,
) -> float:
    """Remaining error budget as a fraction of the allowed errors.

    1.0 means nothing spent; 0.0 means exactly consumed; negative means
    the budget is blown.
    """
    materialized = list(records)
    if not materialized:
        return 1.0
    total = 0
    errors = 0
    for rec in materialized:
        status = rec.get("status")
        if status is None:
            continue
        try:
            code = int(status)
        except (TypeError, ValueError):
            continue
        total += 1
        if code >= 500:
            errors += 1
    if total == 0:
        return 1.0
    allowed = (1 - target_availability) * total
    if allowed <= 0:
        return -float("inf") if errors else 1.0
    return (allowed - errors) / allowed
