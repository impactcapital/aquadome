"""
AquaDome Data Aggregator — SustainaCities DataHub as canonical hub.

Aggregator posture:
  PULL ← external sources (Spexi, dClimate, NOAA AIS, FEMA, AIS Live)
  ADD  ← AquaDome compliance intelligence layer
  PUSH → SustainaCities DataHub (canonical, our platform)
  DISTRIBUTE → AGOL, Ocean Protocol, dClimate series, MiamiVerse

This is what makes AquaDome more than another drone analytics tool:
we become the single pane of glass for waterway intelligence,
aggregating every relevant data source and adding the one thing
no one else provides — statute-aligned compliance verdicts with
chain-of-custody provenance.

City-X.ai brand positioning:
  AquaDome    → waterway compliance product
  City-X.ai   → city tech stack umbrella (this aggregator is its core)
  SustainaCities DataHub → the data marketplace layer
  MiamiVerse  → the 3D urban intelligence viewer

Aggregation runs after each AquaDome pipeline completion and on a
scheduled cadence for passive external source refresh.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import uuid

import httpx

from ..config import settings
from .sustainacities_hub import SustainaCitiesHub, DataHubIngested

logger = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    """Summary of one aggregation run."""
    run_id: uuid.UUID = field(default_factory=uuid.uuid4)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    flight_id: uuid.UUID | None = None

    # Counts per source
    aquadome_entities: int = 0
    spexi_captures_ingested: int = 0
    dclimate_records_ingested: int = 0
    noaa_ais_vessels: int = 0
    fema_events: int = 0

    # Distribution results
    agol_feature_service_url: str | None = None
    ocean_dids: list[str] = field(default_factory=list)
    dclimate_series_updated: list[str] = field(default_factory=list)
    stac_item_id: str | None = None
    miamiverse_layer_refreshed: bool = False

    errors: list[str] = field(default_factory=list)

    @property
    def total_records(self) -> int:
        return (
            self.aquadome_entities
            + self.spexi_captures_ingested
            + self.dclimate_records_ingested
            + self.noaa_ais_vessels
            + self.fema_events
        )


class AquaDomeAggregator:
    """
    Orchestrates the full data aggregation and distribution cycle.

    One call to run_flight_aggregation() after each AquaDome pipeline run:
      1. Ingest contextual data from external sources
      2. Publish AquaDome compliance package to SustainaCities DataHub
      3. Distribute to all configured marketplace channels

    One call to run_scheduled_refresh() on a daily/weekly cron:
      - Refresh external data context (dClimate weather, NOAA AIS)
      - Update stale DataHub items
      - No AquaDome flight required — pure context enrichment

    City-X.ai integration note:
      This aggregator is the data backbone of City-X.ai's waterway module.
      Other City-X.ai products (mobility, energy, housing) can plug into
      the same SustainaCities DataHub using the same STAC catalog pattern.
    """

    def __init__(
        self,
        hub: SustainaCitiesHub,
        tenant_id: str,
        bbox_miami: list[float] | None = None,
        enable_agol: bool = True,
        enable_ocean: bool = True,
        enable_dclimate: bool = True,
    ) -> None:
        self._hub = hub
        self._tenant_id = tenant_id
        # Default to Miami-Dade waterway AOI
        self._bbox = bbox_miami or [-80.40, 25.60, -80.05, 25.90]
        self._enable_agol = enable_agol
        self._enable_ocean = enable_ocean
        self._enable_dclimate = enable_dclimate

    # -------------------------------------------------------------------------
    # Flight-triggered aggregation
    # -------------------------------------------------------------------------

    def run_flight_aggregation(
        self,
        flight_id: uuid.UUID,
        stac_item: dict[str, Any],
        parquet_path: Any,          # Path to GeoParquet
        tileset_url: str | None,
        entity_count: int,
    ) -> AggregationResult:
        """
        Full aggregation cycle triggered by a completed AquaDome flight.
        Should be called by the pipeline orchestrator (e.g., Celery task).
        """
        result = AggregationResult(flight_id=flight_id, aquadome_entities=entity_count)
        logger.info("Starting flight aggregation for flight=%s", flight_id)

        # Step 1: Publish to canonical DataHub
        try:
            item = self._hub.publish_flight_package(stac_item, parquet_path, tileset_url, flight_id)
            result.stac_item_id = item.item_id
            logger.info("Published STAC item %s to DataHub", item.item_id)
        except Exception as exc:
            result.errors.append(f"DataHub publish failed: {exc}")
            logger.error("DataHub publish failed: %s", exc)

        # Step 2: Ingest contextual external data
        noaa_result = self._ingest_noaa_ais_context(flight_id)
        result.noaa_ais_vessels = noaa_result.record_count if noaa_result else 0

        spexi_result = self._ingest_spexi_coverage()
        result.spexi_captures_ingested = spexi_result.record_count if spexi_result else 0

        # Step 3: Distribute to marketplace channels
        if self._enable_agol and result.stac_item_id:
            result.agol_feature_service_url = self._distribute_to_agol(flight_id)

        if self._enable_ocean and result.stac_item_id:
            result.ocean_dids = self._distribute_to_ocean(flight_id)

        if self._enable_dclimate and result.stac_item_id:
            result.dclimate_series_updated = self._distribute_to_dclimate(flight_id)

        # Step 4: Refresh MiamiVerse layer index
        result.miamiverse_layer_refreshed = self._refresh_miamiverse_index()

        result.finished_at = datetime.now(timezone.utc)
        logger.info(
            "Aggregation complete: flight=%s items=%d errors=%d",
            flight_id, result.total_records, len(result.errors),
        )
        return result

    # -------------------------------------------------------------------------
    # Scheduled context refresh (no flight required)
    # -------------------------------------------------------------------------

    def run_scheduled_refresh(
        self,
        lookback_days: int = 7,
    ) -> AggregationResult:
        """
        Scheduled context refresh — runs daily/weekly via cron.
        Refreshes NOAA AIS, dClimate weather context.
        Does not require a new AquaDome flight.
        """
        result = AggregationResult()
        since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        noaa = self._ingest_noaa_ais_context(since=since)
        result.noaa_ais_vessels = noaa.record_count if noaa else 0

        dc = self._ingest_dclimate_weather_context()
        result.dclimate_records_ingested = dc.record_count if dc else 0

        result.miamiverse_layer_refreshed = self._refresh_miamiverse_index()
        result.finished_at = datetime.now(timezone.utc)
        return result

    # -------------------------------------------------------------------------
    # External source ingestors
    # -------------------------------------------------------------------------

    def _ingest_noaa_ais_context(
        self,
        flight_id: uuid.UUID | None = None,
        since: datetime | None = None,
    ) -> DataHubIngested | None:
        """
        Pull NOAA AIS vessel traffic for the Miami AOI.
        Source: MarineCadastre.gov AIS (free, public domain)
        Corroborates AquaDome entity.mmsi with AIS MMSI.

        Downloads the daily bulk CSV/ZIP from MarineCadastre.gov Zone 15
        (Gulf of Mexico / South Florida), saves to a temp file, and ingests
        into the DataHub ``aquadome-noaa-ais`` collection.
        """
        try:
            # Use the flight date or the lookback start as the observation date
            observation_date: datetime = since or datetime.now(timezone.utc) - timedelta(days=1)

            year = observation_date.year
            date_str = observation_date.strftime("%Y_%m_%d")

            # MarineCadastre.gov Zone 15 bulk CSV (Gulf of Mexico covers Miami)
            # Files follow the pattern: Zone15/<year>/<YYYY_MM_DD>.zip
            ais_url = (
                f"https://coast.noaa.gov/htdata/CMSP/AISDataApplications/"
                f"Zone15/{year}/{date_str}.zip"
            )
            logger.info(
                "Downloading NOAA AIS data for %s from %s", date_str, ais_url
            )

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir) / f"ais_{date_str}.zip"

                with httpx.Client(timeout=120.0) as client:
                    resp = client.get(ais_url)

                if not resp.is_success:
                    logger.warning(
                        "NOAA AIS data not available for %s (HTTP %d)",
                        date_str, resp.status_code,
                    )
                    return None

                tmp_path.write_bytes(resp.content)
                logger.info(
                    "Downloaded NOAA AIS %s (%d bytes)", date_str, len(resp.content)
                )

                result = self._hub.ingest_noaa_ais(tmp_path, observation_date)
                logger.info(
                    "NOAA AIS ingested → stac_item_id=%s", result.stac_item_id
                )
                return result

        except Exception as exc:
            logger.warning("NOAA AIS ingest failed: %s", exc)
            return None

    def _ingest_spexi_coverage(self) -> DataHubIngested | None:
        """
        Query Spexi's OGC API for recent captures within the Miami AOI.
        If Spexi has newer base imagery than AquaDome, ingest it as context.
        Spexi's 2.8 cm/px + AquaDome compliance layer = combined product.

        Guards against ImportError if SpexiClient is not yet wired — logs a
        warning and returns None so the aggregation run continues.
        """
        try:
            # Guard: SpexiClient may not be available in all deployments yet
            try:
                from ..integrations.spexi import SpexiClient  # type: ignore[import]
            except ImportError:
                logger.info(
                    "SpexiClient not available (integrations.spexi not installed); "
                    "skipping Spexi coverage ingest"
                )
                return None

            client = SpexiClient()
            captures = client.list_captures(bbox=self._bbox)

            last_result: DataHubIngested | None = None
            for capture in captures:
                last_result = self._hub.ingest_spexi_capture(
                    spexi_capture_id=capture["id"],
                    spexi_geojson=capture["geojson"],
                    tileset_url=capture.get("tileset_url"),
                )
            return last_result

        except Exception as exc:
            logger.warning("Spexi coverage ingest failed: %s", exc)
            return None

    def _ingest_dclimate_weather_context(self) -> DataHubIngested | None:
        """
        Pull dClimate weather context (rainfall, storm surge, wind) for the AOI.
        Used to correlate debris events with weather — evidence for FEMA Section 428.

        Uses the ERA5-Land hourly rainfall series for Miami-Dade, which is the
        most relevant free dClimate dataset for waterway debris correlation.
        """
        try:
            # Known dClimate series ID for Miami-Dade rainfall / weather context
            series_id = "era5_land-hourly-rainfall-miami-dade"
            zarr_url = f"https://gateway.dclimate.net/ipfs/{series_id}"

            now = datetime.now(timezone.utc)
            temporal_start = now - timedelta(days=30)

            result = self._hub.ingest_dclimate_series(
                series_id=series_id,
                zarr_url=zarr_url,
                bbox=self._bbox,
                temporal_start=temporal_start,
                temporal_end=now,
            )
            logger.info("dClimate weather context ingested → %s", result.stac_item_id)
            return result

        except Exception as exc:
            logger.warning("dClimate weather context ingest failed: %s", exc)
            return None

    # -------------------------------------------------------------------------
    # Distribution channels
    # -------------------------------------------------------------------------

    def _distribute_to_agol(self, flight_id: uuid.UUID) -> str | None:
        """
        Publish/update ArcGIS Online Feature Service for this flight.
        Returns service URL or None on failure.

        TODO: Wire to AGOLPublisher.publish_entity_layer() once entities are
        passed through the aggregation pipeline. Requires:
          from ..marketplace.arcgis_online import AGOLPublisher
          publisher = AGOLPublisher.from_config(settings)
          token = publisher.get_token()
          return publisher.publish_entity_layer(flight_id=flight_id, ...)
        """
        try:
            logger.info(
                "AGOL distribution for flight=%s: stubbed (TODO: wire AGOLPublisher)",
                flight_id,
            )
            # Stub URL — replaced by real AGOLPublisher output once wired
            return (
                f"https://services.arcgis.com/placeholder/arcgis/rest/"
                f"services/aquadome_{flight_id}/FeatureServer"
            )
        except Exception as exc:
            logger.error("AGOL distribution failed for flight=%s: %s", flight_id, exc)
            return None

    def _distribute_to_ocean(self, flight_id: uuid.UUID) -> list[str]:
        """
        Publish Ocean Protocol datatokens for this flight's datasets.
        Returns list of DIDs created.

        TODO: Wire to OceanDataPublisher.publish_geoparquet() for all three
        dataset types once OceanDataPublisher is ready. Requires:
          from ..marketplace.ocean_protocol import OceanDataPublisher
          publisher = OceanDataPublisher.from_config(settings)
          return publisher.publish_flight_datasets(flight_id=flight_id)
        """
        try:
            logger.info(
                "Ocean Protocol distribution for flight=%s: stubbed "
                "(TODO: wire OceanDataPublisher)",
                flight_id,
            )
            return []
        except Exception as exc:
            logger.error("Ocean Protocol distribution failed: %s", exc)
            return []

    def _distribute_to_dclimate(self, flight_id: uuid.UUID) -> list[str]:
        """
        Append this flight's data to dClimate series.
        Returns list of updated series IDs.

        TODO: Wire to DClimatePublisher.publish_flight_to_all_series() once
        the dClimate writer interface is finalised. Requires:
          from ..marketplace.dclimate import DClimatePublisher
          publisher = DClimatePublisher.from_config(settings)
          return publisher.publish_flight_to_all_series(flight_id=flight_id)
        """
        try:
            logger.info(
                "dClimate distribution for flight=%s: stubbed "
                "(TODO: wire DClimatePublisher)",
                flight_id,
            )
            return []
        except Exception as exc:
            logger.error("dClimate distribution failed: %s", exc)
            return []

    def _refresh_miamiverse_index(self) -> bool:
        """
        Notify MiamiVerse that new layers are available in the DataHub.
        MiamiVerse re-indexes STAC catalog on webhook signal.

        Reads ``settings.miamiverse_webhook_url`` (env: AQUADOME_MIAMIVERSE_WEBHOOK_URL).
        Returns True on a 2xx response, False otherwise.
        """
        try:
            webhook_url = settings.miamiverse_webhook_url
            if not webhook_url:
                logger.info(
                    "AQUADOME_MIAMIVERSE_WEBHOOK_URL not set; "
                    "skipping MiamiVerse index refresh"
                )
                return False

            resp = httpx.post(
                webhook_url,
                json={"action": "reindex", "bbox": self._bbox},
                timeout=10.0,
            )
            resp.raise_for_status()
            logger.info(
                "MiamiVerse index refresh triggered → HTTP %d", resp.status_code
            )
            return True

        except Exception as exc:
            logger.warning("MiamiVerse index refresh failed: %s", exc)
            return False


# ---------------------------------------------------------------------------
# City-X.ai multi-product aggregation (future)
# ---------------------------------------------------------------------------

class CityXAggregator(AquaDomeAggregator):
    """
    Extended aggregator for the City-X.ai tech stack.

    City-X.ai products share the SustainaCities DataHub — this class
    coordinates cross-product data flows. AquaDome is the first product;
    future City-X.ai products (mobility, energy grid, housing, emergency
    management) add their own ingestors and collections to the same DataHub.

    Shared DataHub collections:
      aquadome-waterways        (this project)
      cityX-mobility-corridors  (future: transit + bike/scooter data)
      cityX-energy-grid         (future: smart meter + EV charging data)
      cityX-housing             (future: Propy + zoning + permits)
      cityX-emergency-mgmt      (future: FEMA BCASE + 911 call hotspots)

    All products publish to MiamiVerse as separate 3D Tile layers —
    city planners see waterway compliance, transit patterns, and energy
    load in the same CesiumJS viewer.
    """

    CITYX_COLLECTIONS = [
        "aquadome-waterways",
        "cityX-mobility-corridors",
        "cityX-energy-grid",
        "cityX-housing",
        "cityX-emergency-mgmt",
    ]

    def get_citywide_dashboard_data(
        self,
        bbox: list[float] | None = None,
        as_of: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Return a unified city intelligence snapshot across all City-X.ai
        products for the MiamiVerse dashboard.
        """
        bbox = bbox or self._bbox
        return self._hub.get_miamiverse_layers(bbox, as_of)
