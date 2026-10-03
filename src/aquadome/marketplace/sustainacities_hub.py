"""
SustainaCities DataHub — canonical data marketplace client.

SustainaCities DataHub is our platform, not a third-party integration.
It is the single source of truth for all City-X.ai waterway data.

External marketplaces (ArcGIS Online, dClimate, Ocean Protocol) are
DISTRIBUTION CHANNELS — we publish TO them and aggregate FROM them,
but the authoritative record always lives here.

Architecture posture:
  AGGREGATE ← from external sources (Spexi, dClimate, NOAA, AIS, FEMA)
  PUBLISH   → to distribution channels (AGOL, Ocean, dClimate, MiamiVerse)
  CANONICAL → SustainaCities DataHub STAC catalog (our platform)

DataHub at: https://sustainacities.com/solution/datahub
STAC API: https://sustainacities.com/stac  (STAC 1.0)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid


@dataclass
class DataHubCollection:
    """A STAC Collection on SustainaCities DataHub."""
    collection_id: str              # e.g. "aquadome-waterways"
    title: str
    description: str
    license: str
    provider: str
    spatial_extent_bbox: list[float]    # [west, south, east, north]
    temporal_extent_start: datetime
    temporal_extent_end: datetime | None = None  # None = ongoing
    keywords: list[str] = field(default_factory=list)
    item_count: int = 0
    public: bool = True


@dataclass
class DataHubItem:
    """A STAC Item on SustainaCities DataHub — one flight's data package."""
    item_id: str
    collection_id: str
    stac_json: dict[str, Any]   # full STAC 1.0 Item
    published_at: datetime
    flight_id: uuid.UUID | None = None
    tileset_url: str | None = None
    parquet_url: str | None = None


@dataclass
class DataHubIngested:
    """Record of an external dataset ingested into the DataHub."""
    source: str                 # "spexi" | "dclimate" | "noaa" | "ais" | "fema"
    external_id: str
    ingested_at: datetime
    stac_item_id: str           # mapped STAC item in our catalog
    collection_id: str
    record_count: int
    bbox: list[float]


class SustainaCitiesHub:
    """
    SustainaCities DataHub API client.

    Dual role:
      PUBLISHER  — push AquaDome flight data to DataHub after each pipeline run
      AGGREGATOR — ingest external environmental datasets for context enrichment

    STAC 1.0 compliant. Supports both sync HTTP (httpx) and async (httpx.AsyncClient).
    Auth: API key in header X-SustainaCities-Key.

    Base URL: https://sustainacities.com/stac
    """

    def __init__(self, api_key: str, base_url: str = "https://sustainacities.com/stac") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "X-SustainaCities-Key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # -------------------------------------------------------------------------
    # PUBLISH — push AquaDome data to canonical DataHub
    # -------------------------------------------------------------------------

    def create_collection(self, collection: DataHubCollection) -> str:
        """
        POST /collections
        Create a new STAC Collection. Returns collection_id.

        AquaDome standard collections:
          aquadome-waterways           — per-flight entity compliance
          aquadome-3d-scenes           — Cesium ion 3D Tilesets per flight
          aquadome-change-detection    — bitemporal debris/dumping events
        """
        _ = collection
        raise NotImplementedError("Wire to httpx.Client: POST {base}/collections")

    def publish_item(self, item: DataHubItem) -> DataHubItem:
        """
        POST /collections/{collection_id}/items
        Publishes a STAC Item (flight data package) to the DataHub.
        Returns the stored item with assigned URLs.
        """
        _ = item
        raise NotImplementedError(
            "Wire to httpx.Client: POST {base}/collections/{id}/items"
        )

    def update_item(self, item: DataHubItem) -> DataHubItem:
        """
        PUT /collections/{collection_id}/items/{item_id}
        Update an existing item (e.g., add tileset URL after Cesium processing).
        """
        _ = item
        raise NotImplementedError(
            "Wire to httpx.Client: PUT {base}/collections/{cid}/items/{iid}"
        )

    def publish_flight_package(
        self,
        stac_json: dict[str, Any],
        parquet_path: Path,
        tileset_url: str | None,
        flight_id: uuid.UUID,
    ) -> DataHubItem:
        """
        Full publish flow for a completed AquaDome flight:
          1. Upload GeoParquet to DataHub storage
          2. POST STAC Item with all asset links
          3. Return published item with canonical URLs

        Called by the pipeline orchestrator after rule engines complete.
        """
        _ = stac_json, parquet_path, tileset_url, flight_id
        raise NotImplementedError("Wire storage upload + STAC item POST")

    # -------------------------------------------------------------------------
    # AGGREGATE — ingest external data into DataHub context
    # -------------------------------------------------------------------------

    def ingest_external(
        self,
        source: str,
        external_id: str,
        stac_item: dict[str, Any],
        target_collection: str,
        record_count: int = 0,
    ) -> DataHubIngested:
        """
        Ingest an external dataset into the DataHub as a STAC Item.
        Maps external metadata (Spexi capture, dClimate series, NOAA buoy)
        into DataHub STAC format and indexes it for MiamiVerse discovery.
        """
        _ = source, external_id, stac_item, target_collection, record_count
        raise NotImplementedError(
            "Wire to httpx.Client: POST {base}/collections/{cid}/items (external STAC)"
        )

    def ingest_spexi_capture(
        self,
        spexi_capture_id: str,
        spexi_geojson: dict[str, Any],
        tileset_url: str | None,
    ) -> DataHubIngested:
        """
        Map a Spexi capture into DataHub as raw-imagery context layer.
        Spexi imagery + AquaDome compliance = combined product.
        """
        _ = spexi_capture_id, spexi_geojson, tileset_url
        raise NotImplementedError("Wire spexi GeoJSON → STAC Item → ingest_external()")

    def ingest_dclimate_series(
        self,
        series_id: str,
        zarr_url: str,
        bbox: list[float],
        temporal_start: datetime,
        temporal_end: datetime | None,
    ) -> DataHubIngested:
        """
        Pull a dClimate climate/weather series into DataHub context.
        Useful for: rainfall correlation with debris events,
        storm/surge context for derelict vessel assessments.
        """
        _ = series_id, zarr_url, bbox, temporal_start, temporal_end
        raise NotImplementedError("Wire dClimate series → STAC Item → ingest_external()")

    def ingest_noaa_ais(
        self,
        ais_geojson_path: Path,
        observation_date: datetime,
    ) -> DataHubIngested:
        """
        Ingest NOAA AIS vessel traffic layer for corroborating vessel identities.
        MMSI from AIS → matched against AquaDome entity.mmsi field.
        Free public data: https://marinecadastre.gov/ais/
        """
        _ = ais_geojson_path, observation_date
        raise NotImplementedError("Wire NOAA AIS GeoJSON → STAC Item → ingest_external()")

    # -------------------------------------------------------------------------
    # QUERY — search the DataHub catalog
    # -------------------------------------------------------------------------

    def search(
        self,
        bbox: list[float] | None = None,
        datetime_range: tuple[datetime, datetime] | None = None,
        collections: list[str] | None = None,
        limit: int = 100,
    ) -> list[DataHubItem]:
        """
        POST /search
        STAC API Item Search. Used by MiamiVerse to discover available layers.
        """
        _ = bbox, datetime_range, collections, limit
        raise NotImplementedError("Wire to httpx.Client: POST {base}/search")

    def get_miamiverse_layers(
        self,
        bbox: list[float],
        as_of: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        Returns all DataHub layers within bbox formatted for MiamiVerse
        CesiumJS layer ingestion — tileset URLs, compliance GeoJSON overlays,
        and contextual data layers (dClimate weather, Spexi base imagery).
        """
        _ = bbox, as_of
        raise NotImplementedError("Wire search() → format for CesiumJS")
