"""Unit tests for DERM trap compliance checker."""

from __future__ import annotations

from datetime import date, datetime, timezone

from aquadome.ontology.enums import SeasonStatus, TrapGearType, TrapLegalStatus
from aquadome.ontology.models import Entity, EntityType
from aquadome.rule_engines.derm import TrapComplianceChecker


def _trap_entity(gear: TrapGearType, prefix: str | None = None) -> Entity:
    now = datetime.now(timezone.utc)
    e = Entity(
        entity_type=EntityType.TRAP,
        first_observed=now,
        last_observed=now,
        gear_type=gear,
        trap_registration_prefix=prefix,
        tenant_id="derm",
    )
    return e


class TestTrapComplianceChecker:
    def setup_method(self):
        self.checker = TrapComplianceChecker()

    def test_blue_crab_in_season_with_prefix_is_lawful(self):
        entity = _trap_entity(TrapGearType.BLUE_CRAB, prefix="B")
        result = self.checker.check(entity, observation_date=date(2025, 6, 15))
        assert result.legal_status == TrapLegalStatus.LAWFUL
        assert result.season_status == SeasonStatus.OPEN

    def test_blue_crab_miami_dade_closure_is_derelict(self):
        """July 10–19 closure in Miami-Dade/Broward/Monroe."""
        entity = _trap_entity(TrapGearType.BLUE_CRAB, prefix="B")
        result = self.checker.check(entity, observation_date=date(2025, 7, 15))
        assert result.season_status == SeasonStatus.CLOSED
        assert result.legal_status == TrapLegalStatus.DERELICT

    def test_blue_crab_wrong_prefix_is_illegal(self):
        entity = _trap_entity(TrapGearType.BLUE_CRAB, prefix="S")
        result = self.checker.check(entity, observation_date=date(2025, 6, 15))
        assert result.legal_status == TrapLegalStatus.ILLEGAL

    def test_unknown_gear_requires_review(self):
        entity = _trap_entity(TrapGearType.UNKNOWN, prefix=None)
        result = self.checker.check(entity)
        assert result.legal_status == TrapLegalStatus.REQUIRES_REVIEW

    def test_no_registration_prefix_is_illegal(self):
        entity = _trap_entity(TrapGearType.STONE_CRAB, prefix=None)
        result = self.checker.check(entity, observation_date=date(2025, 11, 1))
        assert result.legal_status == TrapLegalStatus.ILLEGAL
