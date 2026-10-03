"""Unit tests for canonical ontology models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from aquadome.ontology.models import Observation, ObjectClass, Point2D
from aquadome.ontology.enums import GeolocationSource, HumanReviewStatus
from aquadome.provenance.chain_of_custody import sign_observation


class TestObservationImmutability:
    def test_observation_is_frozen(self, sample_observation):
        with pytest.raises(Exception):
            sample_observation.object_class = ObjectClass.TRAP

    def test_provenance_hash_deterministic(self, sample_observation):
        record1 = sign_observation(sample_observation)
        record2 = sign_observation(sample_observation)
        assert record1.observation_hash == record2.observation_hash

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            Observation(
                flight_id=uuid.uuid4(),
                frame_pts_timestamp=0,
                capture_datetime_utc=datetime.now(timezone.utc),
                geometry=Point2D(lon=-80.19, lat=25.76),
                geolocation_source=GeolocationSource.KLV_CORNER_POINT,
                object_class=ObjectClass.VESSEL,
                class_confidence=1.5,  # invalid: > 1.0
                detector_model_id="rfdetr",
                detector_model_version="1.0.0",
                capture_device_id="DJI-SN1",
                flight_telemetry_hash="abc",
                pipeline_run_id=uuid.uuid4(),
                tenant_id="test",
            )
