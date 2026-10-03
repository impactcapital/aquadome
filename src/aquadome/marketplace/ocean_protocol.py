"""
Ocean Protocol datatoken publisher.

Wraps AkuaDome entity GeoParquet tables as Ocean Protocol datatokens,
enabling decentralized pay-per-query access to compliance-grade
waterway datasets.

Ocean Protocol model:
  - Publisher wraps a dataset with a Datatoken (ERC-20 on Polygon/ETH)
  - Consumers buy 1.0 datatoken → receive a one-time download URL
  - Publisher earns on every purchase; price set by Automated Market Maker
  - Provenance is on-chain; re-ID metadata stays off-chain (privacy)

AkuaDome datasets to publish:
  1. Vessel dwell-time table (GeoParquet) — HB 481 compliance, per flight
  2. FWC at-risk vessel table — anonymized, aggregate
  3. DERM trap compliance table — seasonal compliance snapshots
  4. Change-detection debris table — new illegal dumping events

Privacy design:
  - Never publish hull numbers or vessel owner PII as Ocean datatokens
  - Publish aggregate/statistical summaries for open tiers
  - Publish full compliance records only to verified government consumers
    using Ocean's access control (Compute-to-Data for sensitive records)

Ocean Python SDK: ocean-lib (Apache-2.0)
Docs: https://docs.oceanprotocol.com/building-with-ocean/ocean-cli

Usage:
    publisher = OceanDataPublisher(
        ocean=ocean,  # Ocean instance from ocean-lib
        publisher_wallet=wallet,
        aquadome_tenant_id="marine-patrol",
    )
    did = publisher.publish_dwell_dataset(geoparquet_path, flight_id)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import uuid


@dataclass
class OceanDataset:
    """Published Ocean Protocol dataset asset."""
    did: str                    # Decentralized Identifier (did:op:...)
    datatoken_address: str      # ERC-20 contract address
    datatoken_symbol: str       # e.g. "AKUA-DWELL-1"
    price_ocean: float          # price in OCEAN tokens per access
    metadata_url: str           # DDO (DID Document) URL on-chain
    aquadome_flight_id: uuid.UUID | None = None
    dataset_type: str = "geoparquet"


# Ocean Protocol asset metadata templates aligned with STAC
_DWELL_METADATA = {
    "name": "AkuaDome Vessel Dwell-Time Compliance (HB 481 / FS 327.4108)",
    "description": (
        "Per-vessel anchoring dwell-time classification for Miami waterways. "
        "Fields: entity_id, lat, lon, dwell_days, dwell_status (GREEN/YELLOW/RED), "
        "at_risk_tier, fl_registration_number (hashed), flight_id, capture_datetime_utc. "
        "Statute-aligned to Florida HB 481 / FS 327.4108 (Chapter 2025-39, Laws of FL). "
        "Chain-of-custody: SHA-256 MISB ST 0601 KLV telemetry hash included."
    ),
    "type": "dataset",
    "tags": [
        "waterway", "compliance", "dwell-time", "Florida", "HB-481",
        "marine-patrol", "environmental", "drone", "GeoParquet",
    ],
    "categories": ["Environment", "Government", "Geospatial"],
    "license": "https://market.oceanprotocol.com/terms",
    "author": "SustainaCities LLC / Logos Impact Foundation",
}

_AT_RISK_METADATA = {
    "name": "AkuaDome FWC At-Risk Vessel Early-Warning Dataset",
    "description": (
        "FWC statutory at-risk criteria scores for Miami waterway vessels. "
        "Aggregate only — no PII or individual vessel identifiers. "
        "Fields: entity_id (pseudonymous), at_risk_tier, criteria_count, "
        "canonical_lat, canonical_lon, vtip_eligible, estimated_avoided_cost_usd. "
        "Useful for: insurance underwriting, grant planning, AI spatial model training."
    ),
    "type": "dataset",
    "tags": ["FWC", "at-risk", "derelict-vessel", "environmental", "Florida", "waterway"],
    "categories": ["Environment", "Insurance", "Geospatial"],
    "license": "https://market.oceanprotocol.com/terms",
    "author": "SustainaCities LLC / Logos Impact Foundation",
}

_CHANGE_DETECTION_METADATA = {
    "name": "AkuaDome DERM Waterway Change Detection (Debris / Illegal Dumping)",
    "description": (
        "Bitemporal change events detected between drone flight passes. "
        "Fields: change_id, lat, lon, area_m2, change_type, confidence, "
        "flight_before_id, flight_after_id, detected_at. "
        "change_type: new_debris | debris_removed | vessel_settled | trap_appeared. "
        "Useful for: FEMA Section 428 damage assessment, environmental enforcement."
    ),
    "type": "dataset",
    "tags": ["DERM", "debris", "illegal-dumping", "change-detection", "Miami-Dade", "drone"],
    "categories": ["Environment", "Government", "Geospatial"],
    "license": "https://market.oceanprotocol.com/terms",
    "author": "SustainaCities LLC / Logos Impact Foundation",
}

DATASET_METADATA: dict[str, dict[str, Any]] = {
    "dwell": _DWELL_METADATA,
    "at_risk": _AT_RISK_METADATA,
    "change_detection": _CHANGE_DETECTION_METADATA,
}


class OceanDataPublisher:
    """
    Publishes AkuaDome compliance datasets as Ocean Protocol datatokens.

    Requires ocean-lib: pip install ocean-lib
    Requires a funded wallet on Polygon (MATIC for gas + OCEAN for AMM).

    Compute-to-Data (C2D) mode:
      For sensitive records (full compliance table with hull numbers),
      use Ocean C2D so algorithms run inside a secure enclave —
      consumers never see raw data, only query results.
    """

    def __init__(
        self,
        ocean: Any,             # ocean_lib.ocean.Ocean instance
        publisher_wallet: Any,  # eth_account.Account
        aquadome_tenant_id: str,
        network: str = "polygon",
    ) -> None:
        self._ocean = ocean
        self._wallet = publisher_wallet
        self._tenant_id = aquadome_tenant_id
        self._network = network

    def publish_geoparquet(
        self,
        dataset_type: str,
        parquet_path: Path,
        flight_id: uuid.UUID,
        price_ocean: float = 1.0,
        compute_to_data: bool = False,
    ) -> OceanDataset:
        """
        Publish a GeoParquet compliance dataset as an Ocean datatoken.

        dataset_type: "dwell" | "at_risk" | "change_detection"
        compute_to_data: if True, wraps in C2D pool (sensitive records)

        Returns OceanDataset with DID and datatoken address.
        """
        _ = dataset_type, parquet_path, flight_id, price_ocean, compute_to_data
        raise NotImplementedError(
            "Wire ocean-lib: ocean.assets.create(metadata, publisher_wallet, "
            "files=[UrlFile(url=...)], data_token_amount=1.0)"
        )

    def get_asset_url(self, did: str, consumer_wallet: Any) -> str:
        """
        Consumer flow: purchase 1.0 datatoken → get signed download URL.
        ocean.assets.download_asset(did, consumer_wallet, destination=...)
        """
        _ = did, consumer_wallet
        raise NotImplementedError("Wire ocean-lib: ocean.assets.download_asset()")

    def list_published_assets(self) -> list[OceanDataset]:
        """
        Query Aquarius (Ocean metadata cache) for all assets published
        by this tenant.
        """
        raise NotImplementedError("Wire ocean-lib: ocean.assets.search()")

    # -------------------------------------------------------------------------
    # DePIN token economics (future)
    # -------------------------------------------------------------------------

    def calculate_pilot_earnings(
        self,
        flight_id: uuid.UUID,
        dataset_sales: int,
        price_ocean_per_sale: float,
        pilot_share: float = 0.70,
    ) -> float:
        """
        Calculate OCEAN token earnings for the pilot who flew this flight.

        Proposed revenue split:
          70% → pilot (DePIN supply-side incentive)
          20% → SustainaCities protocol treasury
          10% → AkuaDome data quality staking pool

        This model beats Spexi's centralized coordinator by aligning
        pilot incentives with data quality: pilots with better data
        earn more because buyers rate it higher, driving AMM price up.
        """
        return dataset_sales * price_ocean_per_sale * pilot_share
