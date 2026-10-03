"""Unit tests for the 3D Tiles compliance tagger."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from aquadome.ontology.enums import (
    AtRiskTier,
    DwellStatus,
    EntityType,
    TrapGearType,
    TrapLegalStatus,
)
from aquadome.ontology.models import Entity, Point2D
from aquadome.spatial.tiles3d_tagger import Tiles3DTagger


def _vessel(dwell: DwellStatus | None = None, at_risk: AtRiskTier | None = None) -> Entity:
    return Entity(
        entity_type=EntityType.VESSEL,
        tenant_id="test",
        first_observed=datetime(2025, 1, 1, tzinfo=timezone.utc),
        last_observed=datetime(2025, 6, 1, tzinfo=timezone.utc),
        canonical_geometry=Point2D(lon=-80.19, lat=25.77),
        dwell_status=dwell,
        at_risk_tier=at_risk,
    )


def _trap(status: TrapLegalStatus, gear: TrapGearType = TrapGearType.BLUE_CRAB) -> Entity:
    return Entity(
        entity_type=EntityType.TRAP,
        tenant_id="test",
        first_observed=datetime(2025, 1, 1, tzinfo=timezone.utc),
        last_observed=datetime(2025, 6, 1, tzinfo=timezone.utc),
        canonical_geometry=Point2D(lon=-80.20, lat=25.78),
        trap_legal_status=status,
        gear_type=gear,
    )


class TestTiles3DTagger:

    def setup_method(self) -> None:
        self.tagger = Tiles3DTagger()

    def test_green_vessel_color(self) -> None:
        features = self.tagger.build_overlay([_vessel(dwell=DwellStatus.GREEN)])
        assert len(features) == 1
        assert features[0].display_color == "#2ecc71"
        assert features[0].compliance_label == "DWELL_GREEN"

    def test_yellow_vessel_color(self) -> None:
        features = self.tagger.build_overlay([_vessel(dwell=DwellStatus.YELLOW)])
        assert features[0].display_color == "#f39c12"

    def test_red_vessel_color(self) -> None:
        features = self.tagger.build_overlay([_vessel(dwell=DwellStatus.RED)])
        assert features[0].display_color == "#e74c3c"
        assert features[0].compliance_label == "DWELL_RED"

    def test_at_risk_overrides_dwell_color(self) -> None:
        features = self.tagger.build_overlay(
            [_vessel(dwell=DwellStatus.GREEN, at_risk=AtRiskTier.CRITICAL)]
        )
        # CRITICAL at-risk overrides GREEN dwell color
        assert features[0].display_color == "#c0392b"
        assert "FWC_CRITICAL" in features[0].compliance_label

    def test_illegal_trap_color(self) -> None:
        features = self.tagger.build_overlay([_trap(TrapLegalStatus.ILLEGAL)])
        assert features[0].display_color == "#8e44ad"
        assert features[0].compliance_label == "TRAP_ILLEGAL"

    def test_lawful_trap_color(self) -> None:
        features = self.tagger.build_overlay([_trap(TrapLegalStatus.LAWFUL)])
        assert features[0].display_color == "#27ae60"

    def test_entity_without_geometry_skipped(self) -> None:
        entity = Entity(
            entity_type=EntityType.VESSEL,
            tenant_id="test",
            first_observed=datetime(2025, 1, 1, tzinfo=timezone.utc),
            last_observed=datetime(2025, 6, 1, tzinfo=timezone.utc),
            canonical_geometry=None,  # no geometry
        )
        features = self.tagger.build_overlay([entity])
        assert features == []

    def test_geojson_output_is_valid(self) -> None:
        entities = [
            _vessel(dwell=DwellStatus.RED),
            _trap(TrapLegalStatus.LAWFUL),
        ]
        features = self.tagger.build_overlay(entities)
        geojson_str = self.tagger.to_geojson(features)
        geojson = json.loads(geojson_str)
        assert geojson["type"] == "FeatureCollection"
        assert len(geojson["features"]) == 2
        assert geojson["features"][0]["geometry"]["type"] == "Point"

    def test_3dtiles_schema_count_matches(self) -> None:
        entities = [_vessel(dwell=DwellStatus.GREEN), _trap(TrapLegalStatus.ILLEGAL)]
        features = self.tagger.build_overlay(entities)
        schema_str = self.tagger.to_3dtiles_schema(features)
        schema = json.loads(schema_str)
        assert schema["featureTable"]["count"] == 2
        assert "AquaDomeEntity" in schema["schema"]["classes"]

    def test_geojson_coordinates_correct(self) -> None:
        entities = [_vessel(dwell=DwellStatus.GREEN)]
        features = self.tagger.build_overlay(entities)
        geojson = json.loads(self.tagger.to_geojson(features))
        coords = geojson["features"][0]["geometry"]["coordinates"]
        assert coords == [-80.19, 25.77]
