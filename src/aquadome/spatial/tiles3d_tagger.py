"""
3D Tiles Feature Tagger.

Attaches AkuaDome compliance metadata (dwell_status, at_risk_tier,
trap_legal_status, hull_number) to 3D Tileset features as
3DTILES_metadata batch table properties.

This creates the compliance overlay layer that MiamiVerse renders as
colored billboards over the 3D Gaussian Splat scene:
  GREEN  → anchored vessel, in compliance (HB 481)
  YELLOW → 14-29 days dwell, approaching threshold
  RED    → 30+ days, enforcement candidate ($500/day fine)
  ORANGE → FWC at-risk vessel (early-warning tier)
  PURPLE → derelict / illegal trap gear (DERM)

Output: GeoJSON FeatureCollection + 3DTILES_metadata schema JSON
ready to merge into the Cesium ion tileset root tileset.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
import uuid

from ..ontology.models import Entity
from ..ontology.enums import DwellStatus, AtRiskTier, TrapLegalStatus, EntityType


# MiamiVerse / CesiumJS color conventions for compliance status
_DWELL_COLOR: dict[DwellStatus, str] = {
    DwellStatus.GREEN: "#2ecc71",
    DwellStatus.YELLOW: "#f39c12",
    DwellStatus.RED: "#e74c3c",
}

_AT_RISK_COLOR: dict[AtRiskTier, str] = {
    AtRiskTier.NONE: "#2ecc71",
    AtRiskTier.WATCH: "#f1c40f",
    AtRiskTier.AT_RISK: "#e67e22",
    AtRiskTier.CRITICAL: "#c0392b",
}


@dataclass
class EntityFeature:
    """Compact GeoJSON Feature for one AkuaDome entity."""
    entity_id: uuid.UUID
    entity_type: EntityType
    lon: float
    lat: float
    display_color: str
    compliance_label: str
    properties: dict[str, Any]


class Tiles3DTagger:
    """
    Converts AkuaDome Entity records into a CesiumJS-compatible
    GeoJSON overlay and 3DTILES_metadata schema.

    Usage:
        tagger = Tiles3DTagger()
        overlay = tagger.build_overlay(entities)
        geojson_str = tagger.to_geojson(overlay)
        schema_str = tagger.to_3dtiles_schema(overlay)
    """

    def _entity_to_feature(self, entity: Entity) -> EntityFeature | None:
        if entity.canonical_geometry is None:
            return None

        props: dict[str, Any] = {
            "entity_id": str(entity.entity_id),
            "entity_type": entity.entity_type.value,
            "fl_registration_number": entity.fl_registration_number,
            "hull_color": entity.hull_color,
            "mmsi": entity.mmsi,
            "first_observed": entity.first_observed.isoformat(),
            "last_observed": entity.last_observed.isoformat(),
        }

        color = "#95a5a6"  # unknown/grey default
        label = "UNKNOWN"

        if entity.entity_type == EntityType.VESSEL:
            if entity.dwell_status is not None:
                color = _DWELL_COLOR.get(entity.dwell_status, color)
                label = f"DWELL_{entity.dwell_status.value.upper()}"
                props["dwell_status"] = entity.dwell_status.value
            if entity.at_risk_tier is not None:
                if entity.at_risk_tier in (AtRiskTier.AT_RISK, AtRiskTier.CRITICAL):
                    color = _AT_RISK_COLOR[entity.at_risk_tier]
                    label = f"FWC_{entity.at_risk_tier.value.upper()}"
                props["at_risk_tier"] = entity.at_risk_tier.value
                props["at_risk_criteria_met"] = entity.at_risk_criteria_met

        elif entity.entity_type == EntityType.TRAP:
            if entity.trap_legal_status is not None:
                props["trap_legal_status"] = entity.trap_legal_status.value
                props["gear_type"] = entity.gear_type.value if entity.gear_type else None
                props["trap_registration_prefix"] = entity.trap_registration_prefix
                if entity.trap_legal_status == TrapLegalStatus.ILLEGAL:
                    color = "#8e44ad"
                    label = "TRAP_ILLEGAL"
                elif entity.trap_legal_status == TrapLegalStatus.DERELICT:
                    color = "#6c3483"
                    label = "TRAP_DERELICT"
                elif entity.trap_legal_status == TrapLegalStatus.LAWFUL:
                    color = "#27ae60"
                    label = "TRAP_LAWFUL"

        elif entity.entity_type == EntityType.DEBRIS:
            color = "#7f8c8d"
            label = "DEBRIS"
            props["change_detection_pair_ids"] = entity.change_detection_pair_ids

        return EntityFeature(
            entity_id=entity.entity_id,
            entity_type=entity.entity_type,
            lon=entity.canonical_geometry.lon,
            lat=entity.canonical_geometry.lat,
            display_color=color,
            compliance_label=label,
            properties=props,
        )

    def build_overlay(self, entities: list[Entity]) -> list[EntityFeature]:
        """Convert Entity list to EntityFeature list (skips entities without geometry)."""
        features = []
        for entity in entities:
            f = self._entity_to_feature(entity)
            if f is not None:
                features.append(f)
        return features

    def to_geojson(self, features: list[EntityFeature]) -> str:
        """
        GeoJSON FeatureCollection suitable for CesiumJS DataSource.load()
        or MiamiVerse overlay ingestion.
        """
        geojson = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [f.lon, f.lat],
                    },
                    "properties": {
                        **f.properties,
                        "display_color": f.display_color,
                        "compliance_label": f.compliance_label,
                    },
                }
                for f in features
            ],
        }
        return json.dumps(geojson, indent=2, default=str)

    def to_3dtiles_schema(self, features: list[EntityFeature]) -> str:
        """
        3DTILES_metadata schema JSON for embedding in tileset.json.
        Defines the property table that maps tilesetFeatureId → entity properties.
        """
        schema = {
            "schema": {
                "classes": {
                    "AquaDomeEntity": {
                        "name": "AkuaDome Compliance Entity",
                        "properties": {
                            "entity_id": {"type": "STRING"},
                            "entity_type": {"type": "STRING"},
                            "compliance_label": {"type": "STRING"},
                            "display_color": {"type": "STRING"},
                            "fl_registration_number": {"type": "STRING", "optional": True},
                            "dwell_status": {"type": "STRING", "optional": True},
                            "at_risk_tier": {"type": "STRING", "optional": True},
                            "trap_legal_status": {"type": "STRING", "optional": True},
                        },
                    }
                }
            },
            "featureTable": {
                "class": "AquaDomeEntity",
                "count": len(features),
                "properties": {
                    "entity_id": [str(f.entity_id) for f in features],
                    "entity_type": [f.entity_type.value for f in features],
                    "compliance_label": [f.compliance_label for f in features],
                    "display_color": [f.display_color for f in features],
                },
            },
        }
        return json.dumps(schema, indent=2)
