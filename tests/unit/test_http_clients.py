"""Unit tests for wired HTTP clients — all network calls are mocked."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# AGOLPublisher
# ---------------------------------------------------------------------------

class TestAGOLPublisher:
    def test_get_token_calls_oauth_endpoint(self) -> None:
        """get_token() POSTs to /sharing/rest/oauth2/token and returns access_token."""
        from aquadome.marketplace.arcgis_online import AGOLPublisher

        publisher = AGOLPublisher(
            client_id="test_id",
            client_secret="test_secret",
            org_url="https://miami.maps.arcgis.com",
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"access_token": "tok123", "expires_in": 3600}

        mock_ctx = MagicMock()
        mock_ctx.post.return_value = mock_response

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
            token = publisher.get_token()

        assert token == "tok123"

    def test_get_token_raises_on_error_status(self) -> None:
        """get_token() raises RuntimeError when AGOL returns non-200."""
        from aquadome.marketplace.arcgis_online import AGOLPublisher

        publisher = AGOLPublisher(
            client_id="bad_id",
            client_secret="bad_secret",
            org_url="https://miami.maps.arcgis.com",
        )
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        mock_ctx = MagicMock()
        mock_ctx.post.return_value = mock_response

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
            with pytest.raises(RuntimeError, match="AGOL API error 401"):
                publisher.get_token()

    def test_entities_to_geojson_empty_list(self) -> None:
        """entities_to_geojson returns empty FeatureCollection for no entities."""
        from aquadome.marketplace.arcgis_online import AGOLPublisher

        publisher = AGOLPublisher("id", "secret", "https://miami.maps.arcgis.com")
        flight_id = uuid.uuid4()
        result = publisher.entities_to_geojson([], flight_id)

        assert result["type"] == "FeatureCollection"
        assert result["features"] == []

    def test_entities_to_geojson_skips_entities_without_geometry(self) -> None:
        """entities_to_geojson skips entities that have no canonical_geometry."""
        from aquadome.marketplace.arcgis_online import AGOLPublisher
        from aquadome.ontology.models import Entity
        from aquadome.ontology.enums import EntityType

        publisher = AGOLPublisher("id", "secret", "https://miami.maps.arcgis.com")

        entity = Entity(
            entity_type=EntityType.VESSEL,
            tenant_id="marine-patrol",
            first_observed=datetime.now(timezone.utc),
            last_observed=datetime.now(timezone.utc),
            canonical_geometry=None,  # no geometry
        )
        result = publisher.entities_to_geojson([entity], uuid.uuid4())
        assert result["features"] == []

    def test_entities_to_geojson_includes_compliance_fields(self) -> None:
        """entities_to_geojson includes dwell_stat, at_risk, trap_stat fields."""
        from aquadome.marketplace.arcgis_online import AGOLPublisher
        from aquadome.ontology.models import Entity, Point2D
        from aquadome.ontology.enums import DwellStatus, AtRiskTier, EntityType

        publisher = AGOLPublisher("id", "secret", "https://miami.maps.arcgis.com")

        entity = Entity(
            entity_type=EntityType.VESSEL,
            tenant_id="marine-patrol",
            first_observed=datetime.now(timezone.utc),
            last_observed=datetime.now(timezone.utc),
            canonical_geometry=Point2D(lon=-80.19, lat=25.77),
            dwell_status=DwellStatus.RED,
            at_risk_tier=AtRiskTier.CRITICAL,
        )
        result = publisher.entities_to_geojson([entity], uuid.uuid4())

        assert len(result["features"]) == 1
        props = result["features"][0]["properties"]
        assert props["dwell_stat"] == "red"
        assert props["at_risk"] == "critical"
        assert props["ent_type"] == "Vessel"


# ---------------------------------------------------------------------------
# SpexiClient
# ---------------------------------------------------------------------------

class TestSpexiClient:
    def test_list_captures_returns_features_list(self) -> None:
        """list_captures returns list extracted from GeoJSON FeatureCollection."""
        from aquadome.spatial.spexi import SpexiClient

        client = SpexiClient(api_key="test_key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "type": "FeatureCollection",
            "features": [{"id": "cap1"}, {"id": "cap2"}],
        }

        mock_ctx = MagicMock()
        mock_ctx.get.return_value = mock_response

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
            result = client.list_captures(limit=10)

        assert result == [{"id": "cap1"}, {"id": "cap2"}]

    def test_list_captures_builds_bbox_param(self) -> None:
        """list_captures sends bbox as comma-separated string and passes limit."""
        from aquadome.spatial.spexi import SpexiClient

        client = SpexiClient(api_key="test_key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"type": "FeatureCollection", "features": []}

        captured_params: dict = {}

        def mock_get(url: str, params: dict | None = None, **kwargs: object) -> MagicMock:
            captured_params.update(params or {})
            return mock_response

        mock_ctx = MagicMock()
        mock_ctx.get.side_effect = mock_get

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
            result = client.list_captures(bbox=(-80.35, 25.65, -80.10, 25.85), limit=10)

        assert result == []
        assert captured_params.get("limit") == 10
        bbox_str = captured_params.get("bbox", "")
        assert "-80.35" in bbox_str and "25.65" in bbox_str

    def test_list_captures_raises_on_error(self) -> None:
        """list_captures raises RuntimeError on non-200 response."""
        from aquadome.spatial.spexi import SpexiClient

        client = SpexiClient(api_key="test_key")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        mock_ctx = MagicMock()
        mock_ctx.get.return_value = mock_response

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
            with pytest.raises(RuntimeError, match="Spexi list_captures failed"):
                client.list_captures()


# ---------------------------------------------------------------------------
# CesiumIonUploader
# ---------------------------------------------------------------------------

class TestCesiumIonUploader:
    def test_get_tileset_url_returns_url_from_response(self) -> None:
        """get_tileset_url() returns the url field from the endpoint response."""
        from aquadome.spatial.cesium_ion import CesiumIonUploader

        uploader = CesiumIonUploader(access_token="test_token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "url": "https://assets.cesium.com/12345/tileset.json"
        }

        mock_ctx = MagicMock()
        mock_ctx.get.return_value = mock_response

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
            url = uploader.get_tileset_url(12345)

        assert url == "https://assets.cesium.com/12345/tileset.json"

    def test_get_tileset_url_hits_correct_endpoint(self) -> None:
        """get_tileset_url() calls /v1/assets/{id}/endpoint."""
        from aquadome.spatial.cesium_ion import CesiumIonUploader

        uploader = CesiumIonUploader(access_token="test_token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": "https://assets.cesium.com/99/tileset.json"}

        captured_urls: list[str] = []

        def mock_get(url: str, **kwargs: object) -> MagicMock:
            captured_urls.append(url)
            return mock_response

        mock_ctx = MagicMock()
        mock_ctx.get.side_effect = mock_get

        with patch("httpx.Client") as mock_client_class:
            mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_ctx)
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)
            uploader.get_tileset_url(99)

        assert len(captured_urls) == 1
        assert "/v1/assets/99/endpoint" in captured_urls[0]


# ---------------------------------------------------------------------------
# DClimatePublisher
# ---------------------------------------------------------------------------

class TestDClimatePublisher:
    def _make_publisher(self) -> object:
        from aquadome.marketplace.dclimate import DClimatePublisher

        return DClimatePublisher(
            api_key="test_key",
            wallet_address="0xTEST",
            wallet_private_key="0xPRIVATE",
        )

    def test_publish_flight_calls_all_three_series(self) -> None:
        """publish_flight_to_all_series returns results for dwell, at_risk, change_detection."""
        from aquadome.marketplace.dclimate import DClimatePublisher, DClimatePublishResult

        publisher = DClimatePublisher(
            api_key="test_key",
            wallet_address="0xTEST",
            wallet_private_key="0xPRIVATE",
        )

        flight_id = uuid.uuid4()
        captured_at = datetime.now(timezone.utc)

        mock_result = DClimatePublishResult(
            series_id="test",
            ipfs_cid="Qm123",
            polygon_tx_hash="0x",
            dataset_url="https://api.dclimate.net/test",
            published_at=captured_at,
            record_count=10,
        )

        with patch.object(publisher, "append_data", return_value=mock_result) as mock_append:
            result = publisher.publish_flight_to_all_series(
                Path("/tmp/dwell.parquet"),
                Path("/tmp/at_risk.parquet"),
                Path("/tmp/change.parquet"),
                flight_id,
                captured_at,
            )

        assert set(result.keys()) == {"dwell", "at_risk", "change_detection"}
        assert mock_append.call_count == 3

    def test_publish_flight_passes_correct_series_ids(self) -> None:
        """publish_flight_to_all_series calls append_data with the AQUADOME_SERIES ids."""
        from aquadome.marketplace.dclimate import (
            DClimatePublisher,
            DClimatePublishResult,
            AQUADOME_SERIES,
        )

        publisher = DClimatePublisher(
            api_key="test_key",
            wallet_address="0xTEST",
            wallet_private_key="0xPRIVATE",
        )

        captured_calls: list[str] = []
        captured_at = datetime.now(timezone.utc)

        def fake_append(
            series_id: str, parquet_path: Path, flight_id: uuid.UUID, cap: datetime
        ) -> DClimatePublishResult:
            captured_calls.append(series_id)
            return DClimatePublishResult(
                series_id=series_id,
                ipfs_cid="Qm_fake",
                polygon_tx_hash="0xfake",
                dataset_url=f"https://api.dclimate.net/{series_id}",
                published_at=cap,
                record_count=0,
            )

        with patch.object(publisher, "append_data", side_effect=fake_append):
            publisher.publish_flight_to_all_series(
                Path("/tmp/a.parquet"),
                Path("/tmp/b.parquet"),
                Path("/tmp/c.parquet"),
                uuid.uuid4(),
                captured_at,
            )

        expected_ids = {meta.series_id for meta in AQUADOME_SERIES.values()}
        assert set(captured_calls) == expected_ids


# ---------------------------------------------------------------------------
# OceanDataPublisher
# ---------------------------------------------------------------------------

class TestOceanDataPublisher:
    def test_calculate_pilot_earnings_seventy_percent(self) -> None:
        """70% of revenue goes to pilot by default."""
        from aquadome.marketplace.ocean_protocol import OceanDataPublisher

        publisher = OceanDataPublisher(
            ocean=None,
            publisher_wallet=None,
            aquadome_tenant_id="marine-patrol",
        )

        earnings = publisher.calculate_pilot_earnings(
            flight_id=uuid.uuid4(),
            dataset_sales=100,
            price_ocean_per_sale=2.0,
            pilot_share=0.70,
        )
        assert abs(earnings - 140.0) < 0.001

    def test_calculate_pilot_earnings_uses_share_param(self) -> None:
        """calculate_pilot_earnings respects the pilot_share parameter."""
        from aquadome.marketplace.ocean_protocol import OceanDataPublisher

        publisher = OceanDataPublisher(
            ocean=None,
            publisher_wallet=None,
            aquadome_tenant_id="marine-patrol",
        )

        # 50% share: 10 sales * 5.0 OCEAN * 0.50 = 25.0
        earnings = publisher.calculate_pilot_earnings(
            flight_id=uuid.uuid4(),
            dataset_sales=10,
            price_ocean_per_sale=5.0,
            pilot_share=0.50,
        )
        assert abs(earnings - 25.0) < 0.001

    def test_calculate_pilot_earnings_zero_sales(self) -> None:
        """calculate_pilot_earnings returns 0.0 when there are no sales."""
        from aquadome.marketplace.ocean_protocol import OceanDataPublisher

        publisher = OceanDataPublisher(
            ocean=None,
            publisher_wallet=None,
            aquadome_tenant_id="marine-patrol",
        )

        earnings = publisher.calculate_pilot_earnings(
            flight_id=uuid.uuid4(),
            dataset_sales=0,
            price_ocean_per_sale=2.0,
            pilot_share=0.70,
        )
        assert earnings == 0.0
