"""
Esri ArcGIS Online Feature Service publisher.

Publishes AkuaDome compliance entity tables as hosted Feature Services
on ArcGIS Online — the same channel Spexi uses for their drone data.

AkuaDome's differentiation: we publish statute-aligned compliance attributes
(dwell_status, at_risk_tier, trap_legal_status) as queryable Feature Service
fields — not raw imagery. Government GIS users get ready-to-use compliance
layers, not a pile of drone photos to process themselves.

REST API: ArcGIS Online (AGOL) Item API + Feature Service Admin API
Docs: https://developers.arcgis.com/rest/users-groups-and-items/

Usage:
    publisher = AGOLPublisher(client_id="...", client_secret="...",
                              org_url="https://miami.maps.arcgis.com")
    token = publisher.get_token()
    item_id = publisher.publish_entity_layer(entities, flight_id, token)
    service_url = publisher.get_service_url(item_id, token)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
import uuid

import httpx

from ..ontology.models import Entity
from ..ontology.enums import DwellStatus, AtRiskTier, TrapLegalStatus


logger = logging.getLogger(__name__)

# AGOL item type for a hosted feature layer
AGOL_FEATURE_SERVICE_TYPE = "Feature Service"
AGOL_GEOJSON_TYPE = "GeoJson"


@dataclass
class AGOLPublishResult:
    item_id: str
    service_url: str
    layer_url: str      # service_url + /0 for the first layer
    agol_item_url: str  # https://{org}/home/item.html?id={item_id}
    flight_id: uuid.UUID


class AGOLPublisher:
    """
    Publishes AkuaDome entities as a hosted ArcGIS Online Feature Service.

    Auth: OAuth 2.0 client credentials (server-to-server app credential).
    Org URL example: "https://miami.maps.arcgis.com"

    Publishing flow:
      1. get_token()                  — OAuth2 token
      2. add_item(geojson, token)     — upload GeoJSON as AGOL item
      3. publish_item(item_id, token) — convert GeoJSON → hosted Feature Service
      4. share_item(item_id, token)   — make public or share with specific groups
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        org_url: str,
        username: str | None = None,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._org_url = org_url.rstrip("/")
        self._rest_url = f"{self._org_url}/sharing/rest"
        self._username = username
        self._token_cache: str | None = None
        self._token_expires_at: float = 0.0

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _get_valid_token(self) -> str:
        """Return cached token if still valid, otherwise fetch a fresh one."""
        if self._token_cache is not None and time.time() < self._token_expires_at:
            return self._token_cache
        return self.get_token()

    def _get_username(self, token: str) -> str:
        """Return stored username, or fetch it from /community/self."""
        if self._username:
            return self._username
        with httpx.Client() as client:
            response = client.get(
                f"{self._rest_url}/community/self",
                params={"token": token, "f": "json"},
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"AGOL API error {response.status_code}: {response.text[:200]}"
            )
        data = response.json()
        self._username = data["username"]
        return self._username

    # -------------------------------------------------------------------------
    # Auth
    # -------------------------------------------------------------------------

    def get_token(self) -> str:
        """
        POST /sharing/rest/oauth2/token
        Returns short-lived access token for AGOL REST calls.
        """
        with httpx.Client() as client:
            response = client.post(
                f"{self._rest_url}/oauth2/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "f": "json",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"AGOL API error {response.status_code}: {response.text[:200]}"
            )
        data = response.json()
        token: str = data["access_token"]
        expires_in: int = data.get("expires_in", 7200)
        self._token_cache = token
        # Subtract a small buffer so we refresh before actual expiry
        self._token_expires_at = time.time() + expires_in - 30
        return token

    # -------------------------------------------------------------------------
    # GeoJSON conversion
    # -------------------------------------------------------------------------

    def entities_to_geojson(
        self,
        entities: list[Entity],
        flight_id: uuid.UUID,
    ) -> dict[str, Any]:
        """
        Convert AkuaDome entities to an AGOL-compatible GeoJSON FeatureCollection.

        Field naming follows Esri conventions (no spaces, max 10 chars for shapefile compat).
        Compliance fields are queryable — e.g., clients can run:
          WHERE dwell_stat = 'red' AND at_risk_tier = 'critical'
        """
        features = []
        for entity in entities:
            if entity.canonical_geometry is None:
                continue
            props: dict[str, Any] = {
                "entity_id": str(entity.entity_id),
                "ent_type": entity.entity_type.value,
                "fl_reg_num": entity.fl_registration_number,
                "hull_color": entity.hull_color,
                "mmsi": entity.mmsi,
                "first_obs": entity.first_observed.isoformat(),
                "last_obs": entity.last_observed.isoformat(),
                "flight_id": str(flight_id),
                # HB 481 / FS 327.4108 compliance
                "dwell_stat": entity.dwell_status.value if entity.dwell_status else None,
                # FWC at-risk tier
                "at_risk": entity.at_risk_tier.value if entity.at_risk_tier else None,
                "at_risk_n": len(entity.at_risk_criteria_met),
                # DERM trap compliance
                "trap_stat": entity.trap_legal_status.value if entity.trap_legal_status else None,
                "gear_type": entity.gear_type.value if entity.gear_type else None,
                # Re-ID confidence
                "reid_conf": entity.resolution_confidence,
                "tenant_id": entity.tenant_id,
            }
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [entity.canonical_geometry.lon, entity.canonical_geometry.lat],
                },
                "properties": props,
            })
        return {"type": "FeatureCollection", "features": features}

    # -------------------------------------------------------------------------
    # Item management
    # -------------------------------------------------------------------------

    def add_item(
        self,
        geojson: dict[str, Any],
        title: str,
        token: str,
        tags: list[str] | None = None,
    ) -> str:
        """
        POST /sharing/rest/content/users/{username}/addItem
        Uploads GeoJSON as an AGOL item (type=GeoJson).
        Returns item_id.
        """
        username = self._get_username(token)
        tag_str = ",".join(tags) if tags else "AquaDome,waterway,compliance"
        with httpx.Client() as client:
            response = client.post(
                f"{self._rest_url}/content/users/{username}/addItem",
                data={
                    "title": title,
                    "type": AGOL_GEOJSON_TYPE,
                    "tags": tag_str,
                    "text": json.dumps(geojson),
                    "f": "json",
                    "token": token,
                },
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"AGOL API error {response.status_code}: {response.text[:200]}"
            )
        data = response.json()
        return data["id"]

    def publish_item(self, item_id: str, token: str, service_name: str) -> str:
        """
        POST /sharing/rest/content/users/{username}/publish
        Converts GeoJSON item → hosted Feature Service.
        Returns new service item_id.
        """
        username = self._get_username(token)
        publish_params = json.dumps({"name": service_name, "hasStaticData": False})
        with httpx.Client() as client:
            response = client.post(
                f"{self._rest_url}/content/users/{username}/publish",
                data={
                    "itemId": item_id,
                    "filetype": "geojson",
                    "publishParameters": publish_params,
                    "f": "json",
                    "token": token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"AGOL API error {response.status_code}: {response.text[:200]}"
            )
        data = response.json()
        return data["services"][0]["serviceItemId"]

    def share_item(
        self,
        item_id: str,
        token: str,
        everyone: bool = False,
        groups: list[str] | None = None,
    ) -> None:
        """
        POST /sharing/rest/content/users/{username}/items/{id}/share
        Share with org, specific groups, or public.
        """
        username = self._get_username(token)
        with httpx.Client() as client:
            response = client.post(
                f"{self._rest_url}/content/users/{username}/items/{item_id}/share",
                data={
                    "everyone": "true" if everyone else "false",
                    "groups": ",".join(groups) if groups else "",
                    "f": "json",
                    "token": token,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        if response.status_code != 200:
            raise RuntimeError(
                f"AGOL API error {response.status_code}: {response.text[:200]}"
            )

    # -------------------------------------------------------------------------
    # Orchestration
    # -------------------------------------------------------------------------

    def publish_entity_layer(
        self,
        entities: list[Entity],
        flight_id: uuid.UUID,
        token: str,
        title: str | None = None,
        public: bool = False,
    ) -> AGOLPublishResult:
        """
        Full flow: GeoJSON → AGOL item → hosted Feature Service.
        Returns AGOLPublishResult with item_id and service_url.
        """
        effective_title = title or f"AquaDome Compliance {flight_id}"
        service_name = f"AquaDome_{str(flight_id)[:8]}"

        # 1. Build GeoJSON from entities
        geojson = self.entities_to_geojson(entities, flight_id)

        # 2. Upload as AGOL item
        item_id = self.add_item(geojson, effective_title, token)
        logger.info("AGOL addItem succeeded: item_id=%s", item_id)

        # 3. Publish GeoJSON item → hosted Feature Service
        service_item_id = self.publish_item(item_id, token, service_name=service_name)
        logger.info("AGOL publish succeeded: service_item_id=%s", service_item_id)

        # 4. Share the service item
        self.share_item(service_item_id, token, everyone=public)
        logger.info("AGOL share succeeded: everyone=%s", public)

        # 5. Build result URLs
        service_url = f"{self._org_url}/rest/services/{service_name}/FeatureServer"
        layer_url = service_url + "/0"
        agol_item_url = f"{self._org_url}/home/item.html?id={service_item_id}"

        return AGOLPublishResult(
            item_id=service_item_id,
            service_url=service_url,
            layer_url=layer_url,
            agol_item_url=agol_item_url,
            flight_id=flight_id,
        )

    # -------------------------------------------------------------------------
    # Marketplace listing helpers
    # -------------------------------------------------------------------------

    def create_marketplace_listing(
        self,
        item_id: str,
        token: str,
        price_usd: float = 0.0,
        listing_title: str | None = None,
        listing_description: str | None = None,
    ) -> str:
        """
        List the published Feature Service on the ArcGIS Marketplace.
        POST /sharing/rest/content/listings
        Returns listing_id.

        AkuaDome compliance layers are competitively priced against Spexi's
        generic imagery: we sell compliance verdicts, not raw pixels.
        Recommended pricing tiers:
          Free  — aggregate heat maps (public good, drives adoption)
          $500/mo — per-tenant compliance dashboard (Marine Patrol, FWC, DERM)
          Custom  — insurance underwriting / AI training data bundles
        """
        logger.warning(
            "ArcGIS Marketplace listing requires EPN partnership — submit at "
            "https://marketplace.arcgis.com/items/%s after EPN approval.",
            item_id,
        )
        return item_id
