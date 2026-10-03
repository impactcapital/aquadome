"""Unit tests for the HB 481 / FS 327.4108 dwell-time engine."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from aquadome.ontology.enums import DwellStatus
from aquadome.ontology.models import DwellSegment, Entity, EntityType, Point2D
from aquadome.rule_engines.marine_patrol import DwellTimeEngine


def _entity_with_days(
    eligible_days: float,
    in_mooring: bool = False,
    in_permitted: bool = False,
) -> Entity:
    now = datetime.now(timezone.utc)
    segment = DwellSegment(
        entity_id=uuid.uuid4(),
        start_datetime_utc=now - timedelta(days=eligible_days),
        end_datetime_utc=now,
        geometry_centroid=Point2D(lon=-80.19, lat=25.76),
        in_mooring_field=in_mooring,
        in_permitted_work_area=in_permitted,
    )
    return Entity(
        entity_type=EntityType.VESSEL,
        first_observed=segment.start_datetime_utc,
        last_observed=now,
        dwell_segments=[segment],
        tenant_id="marine-patrol",
    )


class TestDwellTimeEngine:
    def setup_method(self):
        self.engine = DwellTimeEngine()

    def test_green_status_under_14_days(self):
        entity = _entity_with_days(10.0)
        result = self.engine.evaluate(entity)
        assert result.dwell_status == DwellStatus.GREEN
        assert not result.requires_human_review

    def test_yellow_status_14_to_29_days(self):
        entity = _entity_with_days(20.0)
        result = self.engine.evaluate(entity)
        assert result.dwell_status == DwellStatus.YELLOW
        assert result.long_term_permit_applicable

    def test_red_status_30_plus_days(self):
        entity = _entity_with_days(35.0)
        result = self.engine.evaluate(entity)
        assert result.dwell_status == DwellStatus.RED
        assert result.requires_human_review

    def test_mooring_field_excluded(self):
        """Days in a mooring field must not count toward the dwell limit (HB 481)."""
        entity = _entity_with_days(35.0, in_mooring=True)
        result = self.engine.evaluate(entity)
        assert result.eligible_dwell_days == pytest.approx(0.0, abs=0.1)
        assert result.dwell_status == DwellStatus.GREEN

    def test_permitted_work_area_excluded(self):
        entity = _entity_with_days(35.0, in_permitted=True)
        result = self.engine.evaluate(entity)
        assert result.dwell_status == DwellStatus.GREEN

    def test_boundary_exactly_30_days_is_red(self):
        entity = _entity_with_days(30.0)
        result = self.engine.evaluate(entity)
        assert result.dwell_status == DwellStatus.RED
