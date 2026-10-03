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

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

import httpx

logger = logging.getLogger(__name__)


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
        pinata_jwt: str | None = None,
        w3s_token: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._wallet_address = wallet_address
        self._wallet_private_key = wallet_private_key  # kept in env, never logged
        self._base_url = base_url.rstrip("/")
        self._pinata_jwt = pinata_jwt
        self._w3s_token = w3s_token

    def upload_to_ipfs(self, parquet_path: Path) -> str:
        """
        Upload GeoParquet file to IPFS via Pinata or web3.storage.
        Returns IPFS CID (content identifier).

        Pinata is tried first if pinata_jwt is provided; falls back to
        web3.storage if w3s_token is provided instead.
        Both services are free up to their respective limits.
        """
        if self._pinata_jwt is None and self._w3s_token is None:
            raise ValueError("Provide pinata_jwt or w3s_token for IPFS upload")

        if self._pinata_jwt is not None:
            with open(parquet_path, "rb") as fh:
                response = httpx.post(
                    "https://api.pinata.cloud/pinning/pinFileToIPFS",
                    headers={"Authorization": f"Bearer {self._pinata_jwt}"},
                    files={"file": (parquet_path.name, fh, "application/octet-stream")},
                    timeout=120,
                )
            if response.status_code not in (200, 201):
                raise RuntimeError(
                    f"Pinata upload failed: {response.status_code} {response.text[:200]}"
                )
            return response.json()["IpfsHash"]

        # Fall back to web3.storage
        with open(parquet_path, "rb") as fh:
            response = httpx.post(
                "https://api.web3.storage/upload",
                headers={"Authorization": f"Bearer {self._w3s_token}"},
                content=fh.read(),
                timeout=120,
            )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"web3.storage upload failed: {response.status_code} {response.text[:200]}"
            )
        return response.json()["cid"]

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
        response = httpx.post(
            f"{self._base_url}/apiv4/register_dataset",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "dataset_id": metadata.series_id,
                "name": metadata.name,
                "description": metadata.description,
                "unit": metadata.unit,
                "spatial_resolution": metadata.spatial_resolution,
                "temporal_resolution": metadata.temporal_resolution,
                "bbox": list(metadata.bbox),
                "tags": metadata.tags,
                "license": metadata.license,
                "publisher": metadata.publisher,
                "ipfs_cid": ipfs_cid,
                "record_count": record_count,
            },
            timeout=60,
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"dClimate register_dataset failed: {response.status_code} {response.text[:200]}"
            )
        data = response.json()
        return DClimatePublishResult(
            series_id=metadata.series_id,
            ipfs_cid=ipfs_cid,
            polygon_tx_hash=data.get("tx_hash", ""),
            dataset_url=f"{self._base_url}/apiv4/get_station_json/{metadata.series_id}",
            published_at=datetime.now(timezone.utc),
            record_count=record_count,
        )

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
        with open(parquet_path, "rb") as fh:
            response = httpx.post(
                f"{self._base_url}/apiv4/append_data/{series_id}",
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"file": (parquet_path.name, fh, "application/octet-stream")},
                data={
                    "flight_id": str(flight_id),
                    "captured_at": captured_at.isoformat(),
                },
                timeout=120,
            )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"dClimate append_data failed: {response.status_code} {response.text[:200]}"
            )
        data = response.json()
        return DClimatePublishResult(
            series_id=series_id,
            ipfs_cid=data.get("ipfs_cid", ""),
            polygon_tx_hash=data.get("tx_hash", ""),
            dataset_url=f"{self._base_url}/apiv4/get_station_json/{series_id}",
            published_at=datetime.now(timezone.utc),
            record_count=data.get("record_count", 0),
        )

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
        parquet_by_key = {
            "dwell": dwell_parquet,
            "at_risk": at_risk_parquet,
            "change_detection": change_parquet,
        }
        results: dict[str, DClimatePublishResult] = {}
        for key, meta in AQUADOME_SERIES.items():
            parquet = parquet_by_key[key]
            results[key] = self.append_data(meta.series_id, parquet, flight_id, captured_at)
        return results

    def get_subscriber_count(self, series_id: str) -> int:
        """GET /apiv4/dataset/{series_id}/stats — total subscriber count."""
        response = httpx.get(
            f"{self._base_url}/apiv4/dataset/{series_id}/stats",
            headers={"Authorization": f"Bearer {self._api_key}"},
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"dClimate stats failed: {response.status_code} {response.text[:200]}"
            )
        return int(response.json().get("subscriber_count", 0))
