"""
Cesium ion REST API uploader.

Converts drone imagery directories into georeferenced 3D Tilesets
(mesh, point cloud, or Gaussian Splats) via Cesium ion's cloud pipeline.

3D Tiles 2.0 is an OGC standard. CesiumJS is Apache-2.0.
KHR_gaussian_splatting is a Khronos glTF extension (OGC / Cesium / Esri / Niantic collaboration).

REST API reference: https://cesium.com/learn/ion/rest-api/

Usage:
    uploader = CesiumIonUploader(access_token="...")
    asset_id = uploader.create_asset(name, description, imagery_type="IMAGERY")
    uploader.upload_files(asset_id, imagery_dir)
    tileset_url = uploader.wait_for_tileset(asset_id)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid


# Cesium ion imagery type strings
IMAGERY_TYPE_DRONE_PHOTOS = "IMAGERY"
IMAGERY_TYPE_TERRAIN = "TERRAIN"
IMAGERY_TYPE_3D_TILES = "3DTILES"


@dataclass
class CesiumIonAsset:
    asset_id: int
    name: str
    status: str     # "AWAITING_FILES" | "NOT_STARTED" | "IN_PROGRESS" | "COMPLETE" | "ERROR"
    tileset_url: str | None = None
    ion_url: str | None = None       # cesium.com/ion/assets/{id}


class CesiumIonUploader:
    """
    Thin wrapper over Cesium ion REST API v1.

    Endpoints used:
      POST   /v1/assets                           create asset slot
      POST   /v1/assets/{id}/uploadFiles          upload imagery
      POST   /v1/assets/{id}/uploadComplete       signal upload done
      GET    /v1/assets/{id}                      poll tiling status
      GET    /v1/assets/{id}/endpoint             get tileset URL
    """

    _BASE = "https://api.cesium.com"

    def __init__(self, access_token: str) -> None:
        self._token = access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def create_asset(
        self,
        name: str,
        description: str,
        source_type: str = IMAGERY_TYPE_DRONE_PHOTOS,
        options: dict[str, Any] | None = None,
    ) -> CesiumIonAsset:
        """
        POST /v1/assets
        source_type: "IMAGERY" for drone photos → mesh/splat reconstruction
        options: e.g. {"baseTerrainId": 1} to drape over Cesium World Terrain
        Returns CesiumIonAsset with asset_id.
        """
        _ = name, description, source_type, options
        raise NotImplementedError("Wire to httpx.Client: POST {base}/v1/assets")

    def upload_files(self, asset_id: int, imagery_dir: Path) -> None:
        """
        POST /v1/assets/{id}/uploadFiles for each image file.
        Supports JPEG, TIFF (GeoTIFF), and PNG.
        Files > 100 MB use multipart upload.
        """
        _ = asset_id, imagery_dir
        raise NotImplementedError("Wire to httpx.Client: POST {base}/v1/assets/{id}/uploadFiles")

    def signal_upload_complete(self, asset_id: int) -> None:
        """POST /v1/assets/{id}/uploadComplete — starts the tiling job."""
        _ = asset_id
        raise NotImplementedError(
            "Wire to httpx.Client: POST {base}/v1/assets/{id}/uploadComplete"
        )

    def get_asset_status(self, asset_id: int) -> CesiumIonAsset:
        """GET /v1/assets/{id} — returns current tiling status."""
        _ = asset_id
        raise NotImplementedError("Wire to httpx.Client: GET {base}/v1/assets/{id}")

    def get_tileset_url(self, asset_id: int) -> str:
        """
        GET /v1/assets/{id}/endpoint
        Returns the Cesium ion tileset URL for use in CesiumJS:
          ion://assets/{id}  or  https://assets.cesium.com/{id}/tileset.json
        """
        _ = asset_id
        raise NotImplementedError("Wire to httpx.Client: GET {base}/v1/assets/{id}/endpoint")

    def wait_for_tileset(
        self,
        asset_id: int,
        poll_interval_s: int = 30,
        timeout_s: int = 10_800,  # 3 hours
    ) -> str:
        """
        Block until Cesium ion completes tiling.
        Typical drone photogrammetry: 30–120 minutes depending on image count.
        Returns tileset URL.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            asset = self.get_asset_status(asset_id)
            if asset.status == "COMPLETE":
                return self.get_tileset_url(asset_id)
            if asset.status == "ERROR":
                raise RuntimeError(f"Cesium ion tiling failed for asset {asset_id}")
            time.sleep(poll_interval_s)
        raise TimeoutError(f"Cesium ion did not complete asset {asset_id} in {timeout_s}s")

    def ingest_from_splat_url(self, splat_url: str, name: str, flight_id: uuid.UUID) -> CesiumIonAsset:
        """
        Import an existing glTF KHR_gaussian_splatting asset (e.g. from Spexi/Niantic)
        into Cesium ion as a 3D Tiles asset for MiamiVerse delivery.
        POST /v1/assets with type=3DTILES and sourceUrl pointing to the glTF.
        """
        _ = splat_url, name, flight_id
        raise NotImplementedError("Wire to httpx.Client: POST {base}/v1/assets (3DTILES ingest)")
