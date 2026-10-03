"""Shared pytest fixtures for AquaDome tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from aquadome.ontology.models import (
    DwellSegment,
    Entity,
    EntityType,
    Observation,
    ObjectClass,
    Point2D,
)
from aquadome.ontology.enums import GeolocationSource, HumanReviewStatus


@pytest.fixture
def sample_position() -> Point2D:
    return Point2D(lon=-80.1918, lat=25.7617)  # Biscayne Bay, Miami


@pytest.fixture
def sample_observation(sample_position) -> Observation:
    return Observation(
        flight_id=uuid.uuid4(),
        frame_pts_timestamp=1_000_000,
        capture_datetime_utc=datetime(2025, 8, 1, 12, 0, 0, tzinfo=timezone.utc),
        geometry=sample_position,
        geolocation_source=GeolocationSource.KLV_CORNER_POINT,
        object_class=ObjectClass.VESSEL,
        class_confidence=0.92,
        detector_model_id="rfdetr",
        detector_model_version="1.0.0",
        capture_device_id="DJI-MAVIC3E-SN123",
        flight_telemetry_hash="abc123def456",
        pipeline_run_id=uuid.uuid4(),
        tenant_id="marine-patrol",
    )


@pytest.fixture
def vessel_entity_with_dwell(sample_position) -> Entity:
    """Vessel with 32 eligible dwell days in the current 6-month window."""
    now = datetime.now(timezone.utc)
    from datetime import timedelta

    segment = DwellSegment(
        entity_id=uuid.uuid4(),
        start_datetime_utc=now - timedelta(days=32),
        end_datetime_utc=now - timedelta(days=0),
        geometry_centroid=sample_position,
        in_mooring_field=False,
        in_permitted_work_area=False,
    )
    return Entity(
        entity_type=EntityType.VESSEL,
        first_observed=segment.start_datetime_utc,
        last_observed=datetime.now(timezone.utc),
        dwell_segments=[segment],
        tenant_id="marine-patrol",
    )
