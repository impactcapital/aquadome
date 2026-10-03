"""
DERM Trap Compliance Checker

Cross-references detected trap/gear objects against:
  1. FWC commercial trap season calendar (blue crab / stone crab / spiny lobster)
  2. Regional closure periods (e.g., July 10–19 blue-crab closure for Broward/
     Miami-Dade/Monroe counties)
  3. Registration prefix rules (B = blue crab, S = stone crab)

Classification output:
  LAWFUL          — registered, within season, correct prefix
  DERELICT        — out-of-season, not retrieved within ~2 weeks (FWC rule)
  ILLEGAL         — no registration, wrong prefix, or in a closed area
  REQUIRES_REVIEW — OCR failed / ambiguous

DERM internal triage → RECALL-WEIGHTED (missed illegal dumping is costly;
false positives are cheap — a field officer can clear them quickly).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from ...ontology.enums import SeasonStatus, TrapGearType, TrapLegalStatus
from ...ontology.models import Entity


# FWC trap season windows (simplified; production pulls from FWC API/calendar)
# Format: (month, day) inclusive start/end tuples
_BLUE_CRAB_OPEN = True        # no closed season statewide; regional closures apply
_STONE_CRAB_OPEN_START = (10, 15)   # Oct 15
_STONE_CRAB_OPEN_END = (5, 1)       # May 1 (wraps year)
_LOBSTER_MINI_SEASON = [(7, 24), (7, 25)]  # two-day mini-season
_LOBSTER_REGULAR_OPEN_START = (8, 6)
_LOBSTER_REGULAR_OPEN_END = (3, 31)

# Regional closures (Miami-Dade / Broward / Monroe blue-crab closure)
_MIAMI_DADE_BLUE_CRAB_CLOSURE = [(7, 10), (7, 19)]  # July 10–19

# Prefix rules
_VALID_PREFIXES = {"B": TrapGearType.BLUE_CRAB, "S": TrapGearType.STONE_CRAB}


@dataclass
class TrapComplianceResult:
    entity_id: str
    gear_type: TrapGearType
    season_status: SeasonStatus
    legal_status: TrapLegalStatus
    registration_prefix: str | None
    notes: list[str] = field(default_factory=list)


class TrapComplianceChecker:
    """
    Evaluates a trap/gear entity for DERM compliance reporting.

    Usage:
        checker = TrapComplianceChecker()
        result = checker.check(entity, observation_date=date.today())
    """

    def check(self, entity: Entity, observation_date: date | None = None) -> TrapComplianceResult:
        if observation_date is None:
            observation_date = date.today()

        gear = entity.gear_type or TrapGearType.UNKNOWN
        prefix = entity.trap_registration_prefix

        season = self._season_status(gear, observation_date)
        legal = self._legal_status(gear, season, prefix, entity)

        notes: list[str] = []
        if season == SeasonStatus.CLOSED:
            notes.append(f"{gear.value} season CLOSED on {observation_date} — potential derelict gear")
        if legal == TrapLegalStatus.ILLEGAL:
            notes.append("No valid registration prefix — escalate to DERM/FWC")

        return TrapComplianceResult(
            entity_id=str(entity.entity_id),
            gear_type=gear,
            season_status=season,
            legal_status=legal,
            registration_prefix=prefix,
            notes=notes,
        )

    def _season_status(self, gear: TrapGearType, obs_date: date) -> SeasonStatus:
        m, d = obs_date.month, obs_date.day

        if gear == TrapGearType.BLUE_CRAB:
            # Check Miami-Dade regional closure (July 10–19)
            close_start, close_end = _MIAMI_DADE_BLUE_CRAB_CLOSURE
            if (m, d) >= tuple(close_start) and (m, d) <= tuple(close_end):  # type: ignore[arg-type]
                return SeasonStatus.CLOSED
            return SeasonStatus.OPEN

        if gear == TrapGearType.STONE_CRAB:
            start_m, start_d = _STONE_CRAB_OPEN_START
            end_m, end_d = _STONE_CRAB_OPEN_END
            if (m, d) >= (start_m, start_d) or (m, d) <= (end_m, end_d):
                return SeasonStatus.OPEN
            return SeasonStatus.CLOSED

        if gear == TrapGearType.SPINY_LOBSTER:
            mini = [(dm, dd) for dm, dd in _LOBSTER_MINI_SEASON]
            if (m, d) in mini:
                return SeasonStatus.OPEN
            open_start = _LOBSTER_REGULAR_OPEN_START
            open_end = _LOBSTER_REGULAR_OPEN_END
            if (m, d) >= open_start or (m, d) <= open_end:
                return SeasonStatus.OPEN
            return SeasonStatus.CLOSED

        return SeasonStatus.UNKNOWN

    def _legal_status(
        self,
        gear: TrapGearType,
        season: SeasonStatus,
        prefix: str | None,
        entity: Entity,
    ) -> TrapLegalStatus:
        if gear == TrapGearType.UNKNOWN:
            return TrapLegalStatus.REQUIRES_REVIEW

        if season == SeasonStatus.CLOSED:
            return TrapLegalStatus.DERELICT

        if prefix is None:
            return TrapLegalStatus.ILLEGAL

        expected_gear = _VALID_PREFIXES.get(prefix)
        if expected_gear and expected_gear != gear:
            return TrapLegalStatus.ILLEGAL

        return TrapLegalStatus.LAWFUL
