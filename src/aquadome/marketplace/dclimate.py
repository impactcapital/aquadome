"""
dClimate decentralized climate data publisher.

dClimate is a DAO-governed climate data marketplace on Polygon + IPFS.
Publishers monetize environmental datasets via stablecoin payments;
consumers subscribe or pay per-query.

Stack: Polygon (MATIC) + IPFS (Zarr/GeoParquet storage) + Chainlink oracles.
Filecoin Green partnership: carbon offset data only (not general storage).

AkuaDome publishes three environmental dataset series to dClimate:
  1. aquadome.waterway.dwell       — vessel anchoring dwell-time metrics
  2. aquadome.waterway.at_risk     — derelict/at-risk vessel early warning
  3. aquadome.waterway.change      — debris/illegal dumping change events

These are the FIRST waterway-enforcement datasets on dClimate — first-mover
advantage before Spexi/LayerDrone builds this integration.

Docs: https://docs.dclimate.net/
API: https://api.dclimate.net/

Usage:
    publisher = DClimatePublisher(api_key="...", wallet_address="0x...")
    dataset_id = publisher.publish_series(
        series_id="aquadome.waterway.dwell.miami-biscayne-bay",
        parquet_path=path,
        metadata=meta,
    )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import uuid


@dataclass
class DClimateSeriesMetadata:
    """dClimate dataset series descriptor."""
    series_id: str                  # e.g. "aquadome.waterway.dwell.miami"
    name: str
    description: str
    unit: str                       # e.g. "days" for dwell, "count" for at-risk
    spatial_resolution: str         # e.g. "point" or "0.00001deg (~1m)"
    temporal_resolution: str        # e.g. "per-flight" or "daily"
    bbox: tuple[float, float, float, float]  # west, south, east, north
    tags: list[str] = field(default_factory=list)
    license: str = "CC-BY-4.0"
    publisher: str = "SustainaCities LLC / Logos Impact Foundation"
    doi: str | None = None


@dataclass
class DClimatePublishResult:
    series_id: str
    ipfs_cid: str               # IPFS content identifier
    polygon_tx_hash: str        # on-chain registration tx
    dataset_url: str            # https://api.dclimate.net/apiv4/get_station_json/{series_id}
    published_at: datetime
    record_count: int


# AkuaDome series definitions — register these with dClimate once
AQUADOME_SERIES: dict[str, DClimateSeriesMetadata] = {
    "dwell": DClimateSeriesMetadata(
        series_id="aquadome.waterway.dwell.miami",
        name="AkuaDome Miami Waterway Vessel Dwell-Time (HB 481)",
        description=(
            "Per-vessel anchoring dwell-time classification for Miami-Dade waterways. "
            "Statute-aligned to Florida HB 481 / FS 327.4108. "
            "Values: GREEN (0-13 days), YELLOW (14-29 days), RED (30+ days). "
            "Coverage: Biscayne Bay, Miami River, Intracoastal Waterway. "
            "Frequency: per drone flight pass (City of Miami Marine Patrol contract)."
        ),
        unit="days",
        spatial_resolution="point (WGS84)",
        temporal_resolution="per-flight (~weekly)",
        bbox=(-80.35, 25.65, -80.10, 25.85),
        tags=["waterway", "vessel", "compliance", "Florida", "anchoring", "HB-481", "marine"],
    ),
    "at_risk": DClimateSeriesMetadata(
        series_id="aquadome.waterway.at_risk.miami",
        name="AkuaDome Miami FWC At-Risk Vessel Early Warning",
        description=(
            "FWC statutory at-risk criteria count (0-5) per vessel entity. "
            "Aggregate data only — no PII. Entity IDs are pseudonymous UUIDs. "
            "Useful for: insurance underwriting, VTIP grant planning, "
            "AI/ML training for large geospatial models (Spatial AI). "
            "Estimated avoided cost: ~$5,800 per at-risk vessel removed early."
        ),
        unit="criteria_count (0-5)",
        spatial_resolution="point (WGS84)",
        temporal_resolution="per-flight (~weekly)",
        bbox=(-80.35, 25.65, -80.10, 25.85),
        tags=["FWC", "derelict", "at-risk", "environmental", "marine", "Florida"],
    ),
    "change_detection": DClimateSeriesMetadata(
        series_id="aquadome.waterway.change.miami",
        name="AkuaDome Miami DERM Waterway Change Detection",
        description=(
            "Bitemporal debris and illegal dumping change events from drone passes. "
            "Change types: new_debris, debris_removed, vessel_settled, trap_appeared. "
            "Confidence score and area_m2 included. Useful for: FEMA Section 428 "
            "damage assessment, environmental compliance, city planning."
        ),
        unit="events",
        spatial_resolution="point + area_m2 (WGS84)",
        temporal_resolution="per-flight-pair (bitemporal)",
        bbox=(-80.35, 25.65, -80.10, 25.85),
        tags=["debris", "illegal-dumping", "change-detection", "DERM", "Miami-Dade"],
    ),
}


class DClimatePublisher:
    """
    Publishes AkuaDome compliance datasets to the dClimate marketplace.

    Auth: API key for publishing; wallet (Polygon) for on-chain registration.

    Publishing flow:
      1. Format dataset as Zarr or GeoParquet (dClimate accepts both)
      2. Upload to IPFS → get CID
      3. Register series on-chain (Polygon tx)
      4. POST metadata to dClimate API → dataset appears in marketplace

    Consumers access via:
      GET https://api.dclimate.net/apiv4/get_station_json/{series_id}
      (stablecoin subscription via dClimate DAO marketplace)
    """

    def __init__(
        self,
        api_key: str,
        wallet_address: str,
        wallet_private_key: str,
        base_url: str = "https://api.dclimate.net",
    ) -> None:
        self._api_key = api_key
        self._wallet_address = wallet_address
        self._wallet_private_key = wallet_private_key  # kept in env, never logged
        self._base_url = base_url.rstrip("/")

    def upload_to_ipfs(self, parquet_path: Path) -> str:
        """
        Upload GeoParquet file to IPFS via web3.storage or nft.storage.
        Returns IPFS CID (content identifier).

        Both web3.storage and nft.storage are free up to 5GB (Filecoin-backed).
        """
        _ = parquet_path
        raise NotImplementedError(
            "Wire to web3.storage API: POST https://api.web3.storage/upload "
            "with Authorization: Bearer {token}"
        )

    def register_series(
        self,
        metadata: DClimateSeriesMetadata,
        ipfs_cid: str,
        record_count: int,
    ) -> DClimatePublishResult:
        """
        POST /apiv4/register_dataset
        Registers a new dataset series with dClimate's on-chain registry.
        Returns DClimatePublishResult.
        """
        _ = metadata, ipfs_cid, record_count
        raise NotImplementedError("Wire to dClimate API: POST {base}/apiv4/register_dataset")

    def append_data(
        self,
        series_id: str,
        parquet_path: Path,
        flight_id: uuid.UUID,
        captured_at: datetime,
    ) -> DClimatePublishResult:
        """
        Append new observations to an existing dClimate series.
        POST /apiv4/append_data/{series_id}

        AkuaDome publishes after each flight pass — dClimate consumers
        receive near-real-time waterway compliance updates.
        """
        _ = series_id, parquet_path, flight_id, captured_at
        raise NotImplementedError("Wire to dClimate API: POST {base}/apiv4/append_data/{id}")

    def publish_flight_to_all_series(
        self,
        dwell_parquet: Path,
        at_risk_parquet: Path,
        change_parquet: Path,
        flight_id: uuid.UUID,
        captured_at: datetime,
    ) -> dict[str, DClimatePublishResult]:
        """
        Publish all three AkuaDome series in one flight-completion call.
        Returns {series_key: result} for all three series.
        """
        _ = dwell_parquet, at_risk_parquet, change_parquet, flight_id, captured_at
        raise NotImplementedError("Wire append_data calls for all three series")

    def get_subscriber_count(self, series_id: str) -> int:
        """GET /apiv4/dataset/{series_id}/stats — total subscriber count."""
        _ = series_id
        raise NotImplementedError("Wire to dClimate API: GET {base}/apiv4/dataset/{id}/stats")
