"""
Spexi Geospatial API client.

Spexi is the drone pilot network ("the Plexi") that AkuaDome uses for
city-contracted and emergency-response flights. As of May 2026, Spexi routes
captures through Niantic Spatial's Reconstruction API to produce city-scale
georeferenced 3D Gaussian Splats.

API standard: OGC API-Features (GeoJSON + GeoParquet output)
Docs: https://docs.spexi.com

Usage:
    client = SpexiClient(api_key="...", base_url="https://api.spexi.com")
    capture_id = client.upload_flight(imagery_dir, gcps, metadata)
    status = client.poll_reconstruction(capture_id)
    asset_url = status["asset_url"]  # glTF + KHR_gaussian_splatting
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import uuid


@dataclass
class SpexiGCP:
    """Ground Control Point for georeferencing."""
    label: str
    lon: float
    lat: float
    alt_m: float
    pixel_x: float
    pixel_y: float
    image_filename: str


@dataclass
class SpexiFlightMetadata:
    flight_id: uuid.UUID
    tenant_id: str
    hardware_tier: str              # "commercial" | "blue_uas"
    capture_datetime_utc: str       # ISO 8601
    area_of_interest: dict[str, Any]  # GeoJSON polygon
    mission_type: str = "waterway_compliance"
    disaster_response: bool = False


@dataclass
class SpexiReconstructionStatus:
    capture_id: str
    status: str                     # "queued" | "processing" | "complete" | "failed"
    progress_pct: float = 0.0
    asset_url: str | None = None    # glTF KHR_gaussian_splatting URL when complete
    vps_map_id: str | None = None   # Niantic VPS map ID when complete
    tileset_url: str | None = None  # 3D Tiles 2.0 URL when complete
    error_message: str | None = None


class SpexiClient:
    """
    OGC API-Features compatible client for Spexi Geospatial.

    All imagery stays on Spexi's servers; AkuaDome receives only the
    reconstructed asset URLs (no raw pilot imagery re-hosted).
    """

    def __init__(self, api_key: str, base_url: str = "https://api.spexi.com") -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/geo+json",
        }

    def upload_flight(
        self,
        imagery_dir: Path,
        gcps: list[SpexiGCP],
        metadata: SpexiFlightMetadata,
    ) -> str:
        """
        Upload imagery + GCPs to Spexi for reconstruction.
        Returns capture_id for polling.

        Real implementation: multipart POST to /v1/captures
        with imagery files + GCP CSV + metadata JSON.
        """
        # Placeholder — wire to httpx or requests in production
        _ = imagery_dir, gcps, metadata
        raise NotImplementedError(
            "Wire to httpx.Client: POST {base}/v1/captures "
            "with Authorization: Bearer {api_key}"
        )

    def get_reconstruction_status(self, capture_id: str) -> SpexiReconstructionStatus:
        """
        Poll reconstruction status.
        GET /v1/captures/{capture_id}/status
        Returns SpexiReconstructionStatus.
        """
        _ = capture_id
        raise NotImplementedError("Wire to httpx.Client: GET {base}/v1/captures/{id}/status")

    def poll_until_complete(
        self,
        capture_id: str,
        poll_interval_s: int = 60,
        timeout_s: int = 7200,
    ) -> SpexiReconstructionStatus:
        """
        Block until reconstruction completes or times out.
        Typical Spexi reconstruction: 45–90 minutes for a marina-sized AOI.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            status = self.get_reconstruction_status(capture_id)
            if status.status == "complete":
                return status
            if status.status == "failed":
                raise RuntimeError(f"Spexi reconstruction failed: {status.error_message}")
            time.sleep(poll_interval_s)
        raise TimeoutError(f"Spexi reconstruction for {capture_id} did not complete in {timeout_s}s")

    def list_captures(
        self,
        bbox: tuple[float, float, float, float] | None = None,
        tenant_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        OGC API-Features collection listing.
        GET /v1/captures?bbox=...&limit=...
        Returns GeoJSON FeatureCollection items.
        """
        _ = bbox, tenant_id, limit
        raise NotImplementedError("Wire to httpx.Client: GET {base}/v1/captures")
