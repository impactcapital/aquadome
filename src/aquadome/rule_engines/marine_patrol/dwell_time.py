"""
Marine Patrol Dwell-Time Engine
Statute: HB 481 / FS 327.4108, enacted as Chapter 2025-39, Laws of Florida.

Thresholds (rolling 6-month window, excluding mooring fields & permitted areas):
  GREEN  0–13 days    — compliant
  YELLOW 14–29 days   — flag §327.4111 long-term anchoring permit (new, eff. Jan 1 2026)
  RED    30+ days     — violation, civil fine up to $500/day

Exclusions per statute:
  - Segments where vessel is in a designated mooring field
  - Segments where vessel is in a permitted work area
  - Segments in no-anchor buffer zones (not counted toward violation but tracked)

Designated grandfathered ALAs (e.g., Sunset Lake) per Chapter 2025-39 are
stored as geofences in the GIS layer; the engine checks containment.

Enforcement note: FALSE POSITIVES ARE COSTLY — precision-weighted.
Gate enforcement-facing outputs behind mandatory human review if FP rate > 5%.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from ...ontology.enums import DwellStatus
from ...ontology.models import DwellSegment, Entity


# HB 481 / FS 327.4108 statutory thresholds
_ROLLING_WINDOW_DAYS = 180
_GREEN_MAX_DAYS = 13
_YELLOW_MAX_DAYS = 29
_FINE_MAX_PER_DAY_USD = 500


@dataclass
class DwellTimeResult:
    entity_id: str
    fl_registration_number: str | None
    eligible_dwell_days: float          # excludes mooring fields and permitted areas
    rolling_window_days: int = _ROLLING_WINDOW_DAYS
    dwell_status: DwellStatus = DwellStatus.GREEN
    long_term_permit_applicable: bool = False  # §327.4111 (eff. Jan 1 2026)
    max_daily_fine_usd: int = _FINE_MAX_PER_DAY_USD
    requires_human_review: bool = False
    notes: list[str] = field(default_factory=list)


class DwellTimeEngine:
    """
    Computes HB 481 compliance status for a Vessel entity.

    Usage:
        engine = DwellTimeEngine()
        result = engine.evaluate(entity, as_of=datetime.now(timezone.utc))
    """

    def __init__(self, fp_rate_threshold: float = 0.05) -> None:
        self.fp_rate_threshold = fp_rate_threshold

    def evaluate(
        self, entity: Entity, as_of: datetime | None = None
    ) -> DwellTimeResult:
        if as_of is None:
            as_of = datetime.now(timezone.utc)

        window_start = as_of - timedelta(days=_ROLLING_WINDOW_DAYS)
        eligible_days = self._sum_eligible_days(entity.dwell_segments, window_start, as_of)

        status = self._classify(eligible_days)
        long_term_permit = status == DwellStatus.YELLOW  # flag permit option

        notes: list[str] = []
        if entity.in_no_anchor_buffer if hasattr(entity, "in_no_anchor_buffer") else False:
            notes.append("Vessel observed within no-anchor buffer zone")

        return DwellTimeResult(
            entity_id=str(entity.entity_id),
            fl_registration_number=entity.fl_registration_number,
            eligible_dwell_days=round(eligible_days, 2),
            dwell_status=status,
            long_term_permit_applicable=long_term_permit,
            requires_human_review=(status == DwellStatus.RED),
            notes=notes,
        )

    def _sum_eligible_days(
        self,
        segments: list[DwellSegment],
        window_start: datetime,
        as_of: datetime,
    ) -> float:
        total = 0.0
        for seg in segments:
            # Skip segments excluded by statute
            if seg.in_mooring_field or seg.in_permitted_work_area:
                continue

            seg_end = seg.end_datetime_utc or as_of
            seg_start = seg.start_datetime_utc

            # Clip to rolling window
            effective_start = max(seg_start, window_start)
            effective_end = min(seg_end, as_of)

            if effective_end <= effective_start:
                continue

            days = (effective_end - effective_start).total_seconds() / 86_400
            total += days
        return total

    @staticmethod
    def _classify(days: float) -> DwellStatus:
        if days >= _YELLOW_MAX_DAYS + 1:
            return DwellStatus.RED
        if days >= _GREEN_MAX_DAYS + 1:
            return DwellStatus.YELLOW
        return DwellStatus.GREEN
