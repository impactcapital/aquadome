"""
STAC 1.0 Item builder for the SustainaCities DataHub.

Produces a STAC Item JSON for each AkuaDome flight that includes:
  - eo extension: sensor / spectral metadata
  - label extension: per-entity compliance annotations
  - aquadome: custom extension namespace (dwell_status, at_risk_tier, etc.)

The STAC Item links to:
  - The Cesium ion tileset URL (3D Tiles asset)
  - The GeoParquet entity table (data link)
  - The compliance report PDF (derived link)

SustainaCities DataHub ingests STAC 1.0 collections at:
  https://sustainacities.com/solution/datahub

MiamiVerse can discover georeferenced 3D Tiles layers via the STAC catalog
using the `3d-tiles` asset role.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


STAC_VERSION = "1.0.0"
AQUADOME_EXTENSION = "https://schemas.akuadome.io/stac/v1/aquadome-ext.json"


@dataclass
class STACBbox:
    west: float
    south: float
    east: float
    north: float

    def as_list(self) -> list[float]:
        return [self.west, self.south, self.east, self.north]


@dataclass
class STACAssetLink:
    href: str
    type: str
    title: str
    roles: list[str] = field(default_factory=list)


@dataclass
class AquaDomeSTACProperties:
    """aquadome: extension properties on a STAC Item."""
    flight_id: uuid.UUID
    tenant_id: str
    hardware_tier: str          # "commercial" | "blue_uas"
    pilot_cert_id: str | None
    telemetry_hash: str         # SHA-256 chain-of-custody
    entity_count: int
    vessel_count: int
    red_dwell_count: int        # HB 481 RED-status vessels
    at_risk_count: int          # FWC at-risk vessels
    illegal_trap_count: int     # DERM illegal trap gear
    disaster_response: bool = False


class STACCatalogBuilder:
    """
    Builds a STAC 1.0 Item for a completed AkuaDome flight.

    The Item is ready to POST to any STAC API endpoint:
      POST https://sustainacities.com/stac/collections/aquadome-waterways/items
    """

    def build_item(
        self,
        *,
        item_id: str,
        flight_datetime: datetime,
        bbox: STACBbox,
        footprint_geojson: dict[str, Any],
        tileset_asset: STACAssetLink,
        entity_parquet_asset: STACAssetLink,
        report_pdf_asset: STACAssetLink | None,
        props: AquaDomeSTACProperties,
    ) -> dict[str, Any]:
        """
        Returns a STAC 1.0 Item dict ready for JSON serialization.

        Follows the eo, label, and aquadome extension namespaces.
        """
        dt_str = flight_datetime.astimezone(timezone.utc).isoformat()

        assets: dict[str, Any] = {
            "3d-tileset": {
                "href": tileset_asset.href,
                "type": tileset_asset.type,
                "title": tileset_asset.title,
                "roles": tileset_asset.roles or ["3d-tiles", "visual"],
            },
            "entity-table": {
                "href": entity_parquet_asset.href,
                "type": entity_parquet_asset.type,
                "title": entity_parquet_asset.title,
                "roles": entity_parquet_asset.roles or ["data", "geoparquet"],
            },
        }
        if report_pdf_asset:
            assets["compliance-report"] = {
                "href": report_pdf_asset.href,
                "type": "application/pdf",
                "title": report_pdf_asset.title,
                "roles": ["derived"],
            }

        item: dict[str, Any] = {
            "type": "Feature",
            "stac_version": STAC_VERSION,
            "stac_extensions": [
                "https://stac-extensions.github.io/eo/v1.0.0/schema.json",
                "https://stac-extensions.github.io/label/v1.0.1/schema.json",
                AQUADOME_EXTENSION,
            ],
            "id": item_id,
            "geometry": footprint_geojson,
            "bbox": bbox.as_list(),
            "properties": {
                "datetime": dt_str,
                # eo extension
                "eo:cloud_cover": None,
                "platform": f"drone/{props.hardware_tier}",
                # aquadome extension
                "aquadome:flight_id": str(props.flight_id),
                "aquadome:tenant_id": props.tenant_id,
                "aquadome:hardware_tier": props.hardware_tier,
                "aquadome:pilot_cert_id": props.pilot_cert_id,
                "aquadome:telemetry_hash": props.telemetry_hash,
                "aquadome:entity_count": props.entity_count,
                "aquadome:vessel_count": props.vessel_count,
                "aquadome:red_dwell_count": props.red_dwell_count,
                "aquadome:at_risk_count": props.at_risk_count,
                "aquadome:illegal_trap_count": props.illegal_trap_count,
                "aquadome:disaster_response": props.disaster_response,
                # label extension
                "label:type": "vector",
                "label:tasks": ["classification", "object-detection"],
                "label:classes": [
                    {"name": "vessel", "classes": ["green", "yellow", "red"]},
                    {"name": "trap", "classes": ["lawful", "illegal", "requires_review"]},
                    {"name": "debris", "classes": ["new", "removed"]},
                ],
            },
            "links": [
                {
                    "rel": "collection",
                    "href": "https://sustainacities.com/stac/collections/aquadome-waterways",
                    "type": "application/json",
                },
                {
                    "rel": "root",
                    "href": "https://sustainacities.com/stac",
                    "type": "application/json",
                },
            ],
            "assets": assets,
            "collection": "aquadome-waterways",
        }
        return item

    def to_json(self, item: dict[str, Any], indent: int = 2) -> str:
        return json.dumps(item, indent=indent, default=str)
