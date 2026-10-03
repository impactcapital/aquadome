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

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import uuid

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


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
    # Core HTTP helper — all methods funnel through here
    # -------------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(
            (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError)
        ),
        reraise=True,
    )
    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """
        Execute an HTTP request against the DataHub STAC API.

        Builds the full URL, injects auth and Accept headers, and raises a
        meaningful error on any non-2xx response (includes status code and a
        snippet of the response body). Tenacity retries up to 3 times with
        exponential back-off on network / timeout / server errors.

        Args:
            method: HTTP verb, e.g. "GET", "POST", "PUT".
            path:   Path relative to base_url, e.g. "/collections".
            **kwargs: Forwarded verbatim to ``httpx.Client.request``.
                      Pass ``json=`` for JSON bodies or ``files=`` for
                      multipart uploads (Content-Type is omitted in that
                      case so httpx can set the boundary automatically).
        """
        url = f"{self._base_url}{path}"

        # Base headers — omit Content-Type for multipart so httpx sets boundary
        headers: dict[str, str] = {
            "X-SustainaCities-Key": self._api_key,
            "Accept": "application/json",
        }
        if "files" not in kwargs:
            headers["Content-Type"] = "application/json"

        # Let callers override / extend headers
        caller_headers: dict[str, str] = kwargs.pop("headers", {})
        headers.update(caller_headers)

        logger.debug("DataHub %s %s", method, url)
        with httpx.Client(timeout=30.0) as client:
            resp = client.request(method, url, headers=headers, **kwargs)

        if not resp.is_success:
            snippet = resp.text[:300]
            raise httpx.HTTPStatusError(
                f"SustainaCities {method} {path} → HTTP {resp.status_code}: {snippet}",
                request=resp.request,
                response=resp,
            )

        return resp

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
        temporal_end: str | None = (
            collection.temporal_extent_end.isoformat()
            if collection.temporal_extent_end
            else None
        )
        body: dict[str, Any] = {
            "type": "Collection",
            "id": collection.collection_id,
            "stac_version": "1.0.0",
            "title": collection.title,
            "description": collection.description,
            "license": collection.license,
            "providers": [{"name": collection.provider, "roles": ["producer"]}],
            "extent": {
                "spatial": {"bbox": [collection.spatial_extent_bbox]},
                "temporal": {
                    "interval": [
                        [collection.temporal_extent_start.isoformat(), temporal_end]
                    ]
                },
            },
            "keywords": collection.keywords,
            "links": [],
        }
        self._request("POST", "/collections", json=body)
        logger.info("Created DataHub collection: %s", collection.collection_id)
        return collection.collection_id

    def publish_item(self, item: DataHubItem) -> DataHubItem:
        """
        POST /collections/{collection_id}/items
        Publishes a STAC Item (flight data package) to the DataHub.
        Returns the stored item with assigned URLs.
        """
        resp = self._request(
            "POST",
            f"/collections/{item.collection_id}/items",
            json=item.stac_json,
        )
        data: dict[str, Any] = resp.json()
        assets: dict[str, Any] = data.get("assets", {})
        item.tileset_url = (
            assets.get("tileset", {}).get("href") or item.tileset_url
        )
        item.parquet_url = (
            assets.get("data", {}).get("href") or item.parquet_url
        )
        logger.info(
            "Published STAC item %s to collection %s",
            item.item_id, item.collection_id,
        )
        return item

    def update_item(self, item: DataHubItem) -> DataHubItem:
        """
        PUT /collections/{collection_id}/items/{item_id}
        Update an existing item (e.g., add tileset URL after Cesium processing).
        """
        resp = self._request(
            "PUT",
            f"/collections/{item.collection_id}/items/{item.item_id}",
            json=item.stac_json,
        )
        data: dict[str, Any] = resp.json()
        assets: dict[str, Any] = data.get("assets", {})
        item.tileset_url = (
            assets.get("tileset", {}).get("href") or item.tileset_url
        )
        item.parquet_url = (
            assets.get("data", {}).get("href") or item.parquet_url
        )
        logger.info(
            "Updated STAC item %s in collection %s",
            item.item_id, item.collection_id,
        )
        return item

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
        # 1. Upload GeoParquet via multipart POST /upload
        logger.info("Uploading GeoParquet for flight %s: %s", flight_id, parquet_path)
        with parquet_path.open("rb") as fh:
            upload_resp = self._request(
                "POST",
                "/upload",
                files={
                    "file": (
                        parquet_path.name,
                        fh,
                        "application/vnd.apache.parquet",
                    )
                },
            )
        parquet_url: str = upload_resp.json().get("url", "")
        logger.info("GeoParquet uploaded → %s", parquet_url)

        # 2. Build STAC Item with full asset links
        item_id: str = stac_json.get("id", str(flight_id))
        collection_id: str = stac_json.get("collection", "aquadome-waterways")
        now = datetime.now(timezone.utc)

        assets: dict[str, Any] = {
            "data": {
                "href": parquet_url,
                "type": "application/vnd.apache.parquet",
                "roles": ["data"],
                "title": "AquaDome GeoParquet entity data",
            }
        }
        if tileset_url:
            assets["tileset"] = {
                "href": tileset_url,
                "type": "application/json",
                "roles": ["visual"],
                "title": "Cesium ion 3D Tileset",
            }

        full_stac: dict[str, Any] = {
            **stac_json,
            "assets": {**stac_json.get("assets", {}), **assets},
        }

        item = DataHubItem(
            item_id=item_id,
            collection_id=collection_id,
            stac_json=full_stac,
            published_at=now,
            flight_id=flight_id,
            tileset_url=tileset_url,
            parquet_url=parquet_url,
        )

        # 3. POST STAC Item
        return self.publish_item(item)

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
        now = datetime.now(timezone.utc)

        # Ensure collection field is set on the STAC item
        stac_item.setdefault("collection", target_collection)

        self._request(
            "POST",
            f"/collections/{target_collection}/items",
            json=stac_item,
        )

        bbox: list[float] = stac_item.get("bbox", [])
        stac_item_id: str = stac_item.get("id", external_id)

        logger.info(
            "Ingested external item %s (source=%s) → collection %s",
            stac_item_id, source, target_collection,
        )
        return DataHubIngested(
            source=source,
            external_id=external_id,
            ingested_at=now,
            stac_item_id=stac_item_id,
            collection_id=target_collection,
            record_count=record_count,
            bbox=bbox,
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
        now = datetime.now(timezone.utc)

        # Handle both plain Feature and FeatureCollection
        if spexi_geojson.get("type") == "FeatureCollection":
            first = spexi_geojson.get("features", [{}])[0]
            geometry: dict[str, Any] = first.get("geometry", {})
            props: dict[str, Any] = first.get("properties") or {}
        else:
            geometry = spexi_geojson.get("geometry") or {}
            props = spexi_geojson.get("properties") or {}

        bbox: list[float] = (
            spexi_geojson.get("bbox")
            or props.get("bbox")
            or []
        )

        assets: dict[str, Any] = {
            "raw_imagery": {
                "href": props.get(
                    "download_url",
                    f"spexi://capture/{spexi_capture_id}",
                ),
                "type": "image/tiff; application=geotiff",
                "roles": ["data"],
                "title": "Spexi raw imagery (2.8 cm/px)",
            }
        }
        if tileset_url:
            assets["tileset"] = {
                "href": tileset_url,
                "type": "application/json",
                "roles": ["visual"],
                "title": "Spexi 3D Tileset",
            }

        captured_at: str = props.get("captured_at", now.isoformat())
        stac_item: dict[str, Any] = {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": f"spexi-{spexi_capture_id}",
            "collection": "aquadome-external-imagery",
            "geometry": geometry,
            "bbox": bbox,
            "properties": {
                "datetime": captured_at,
                "platform": "spexi",
                "gsd": props.get("gsd", 0.028),  # 2.8 cm/px
                "spexi:capture_id": spexi_capture_id,
            },
            "assets": assets,
            "links": [],
        }

        return self.ingest_external(
            source="spexi",
            external_id=spexi_capture_id,
            stac_item=stac_item,
            target_collection="aquadome-external-imagery",
            record_count=1,
        )

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
        temporal_end_iso: str | None = (
            temporal_end.isoformat() if temporal_end else None
        )

        # Build bbox polygon geometry from [west, south, east, north]
        if len(bbox) >= 4:
            west, south, east, north = bbox[0], bbox[1], bbox[2], bbox[3]
        else:
            west, south, east, north = 0.0, 0.0, 0.0, 0.0

        geometry: dict[str, Any] = {
            "type": "Polygon",
            "coordinates": [[
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]],
        }

        stac_item: dict[str, Any] = {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": f"dclimate-{series_id}",
            "collection": "aquadome-climate-context",
            "geometry": geometry,
            "bbox": bbox,
            "properties": {
                "datetime": None,
                "start_datetime": temporal_start.isoformat(),
                "end_datetime": temporal_end_iso,
                "platform": "dclimate",
                "dclimate:series_id": series_id,
            },
            "assets": {
                "zarr": {
                    "href": zarr_url,
                    "type": "application/vnd+zarr",
                    "roles": ["data"],
                    "title": "dClimate Zarr series",
                }
            },
            "links": [],
        }

        return self.ingest_external(
            source="dclimate",
            external_id=series_id,
            stac_item=stac_item,
            target_collection="aquadome-climate-context",
            record_count=1,
        )

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
        date_str: str = observation_date.date().isoformat()

        # Miami-Dade AOI bounding box
        miami_bbox: list[float] = [-80.40, 25.60, -80.05, 25.90]

        stac_item: dict[str, Any] = {
            "type": "Feature",
            "stac_version": "1.0.0",
            "id": f"noaa-ais-{date_str}",
            "collection": "aquadome-noaa-ais",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [-80.40, 25.60],
                    [-80.05, 25.60],
                    [-80.05, 25.90],
                    [-80.40, 25.90],
                    [-80.40, 25.60],
                ]],
            },
            "bbox": miami_bbox,
            "properties": {
                "datetime": observation_date.isoformat(),
                "platform": "noaa",
                "noaa:source": "marinecadastre.gov",
                "noaa:file": str(ais_geojson_path),
                "noaa:observation_date": date_str,
            },
            "assets": {
                "ais_data": {
                    "href": str(ais_geojson_path),
                    "type": "application/geo+json",
                    "roles": ["data"],
                    "title": "NOAA AIS vessel tracks",
                }
            },
            "links": [],
        }

        return self.ingest_external(
            source="noaa",
            external_id=f"noaa-ais-{date_str}",
            stac_item=stac_item,
            target_collection="aquadome-noaa-ais",
            record_count=1,
        )

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
        body: dict[str, Any] = {"limit": limit}
        if bbox:
            body["bbox"] = bbox
        if datetime_range:
            start, end = datetime_range
            body["datetime"] = f"{start.isoformat()}/{end.isoformat()}"
        if collections:
            body["collections"] = collections

        resp = self._request("POST", "/search", json=body)
        data: dict[str, Any] = resp.json()

        now = datetime.now(timezone.utc)
        items: list[DataHubItem] = []
        for feature in data.get("features", []):
            assets: dict[str, Any] = feature.get("assets", {})
            items.append(
                DataHubItem(
                    item_id=feature.get("id", ""),
                    collection_id=feature.get("collection", ""),
                    stac_json=feature,
                    published_at=now,
                    tileset_url=assets.get("tileset", {}).get("href"),
                    parquet_url=assets.get("data", {}).get("href"),
                )
            )
        return items

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
        dt_range: tuple[datetime, datetime] | None = None
        if as_of:
            # Search the 90-day window ending at as_of
            start = as_of - timedelta(days=90)
            dt_range = (start, as_of)

        items = self.search(bbox=bbox, datetime_range=dt_range)

        layers: list[dict[str, Any]] = []
        for item in items:
            assets: dict[str, Any] = item.stac_json.get("assets", {})
            props: dict[str, Any] = item.stac_json.get("properties", {})

            tileset_url: str | None = (
                assets.get("tileset", {}).get("href") or item.tileset_url
            )
            geojson_url: str | None = (
                assets.get("data", {}).get("href")
                or assets.get("ais_data", {}).get("href")
                or assets.get("raw_imagery", {}).get("href")
                or item.parquet_url
            )

            layers.append({
                "layer_id": item.item_id,
                "type": item.collection_id,
                "tileset_url": tileset_url,
                "geojson_url": geojson_url,
                "compliance_attributes": props,
                "bbox": item.stac_json.get("bbox", []),
                "datetime": (
                    props.get("datetime") or props.get("start_datetime")
                ),
            })

        return layers
