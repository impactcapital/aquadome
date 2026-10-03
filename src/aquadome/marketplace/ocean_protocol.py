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

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

import httpx

logger = logging.getLogger(__name__)


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
        aquarius_url: str = "https://v4.aquarius.oceanprotocol.com",
        provider_url: str = "https://v4.provider.oceanprotocol.com",
    ) -> None:
        self._ocean = ocean
        self._wallet = publisher_wallet
        self._tenant_id = aquadome_tenant_id
        self._network = network
        self._aquarius_url = aquarius_url.rstrip("/")
        self._provider_url = provider_url.rstrip("/")

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

        Note: On-chain NFT mint and datatoken creation requires web3.py + funded
        Polygon wallet. This method handles DDO pre-registration; call
        ocean-lib's ocean.assets.create() for the full on-chain flow.
        """
        did = f"did:op:{hashlib.sha256(f'{dataset_type}:{flight_id}'.encode()).hexdigest()}"
        metadata = DATASET_METADATA.get(dataset_type, DATASET_METADATA["dwell"])
        now_iso = datetime.now(timezone.utc).isoformat()
        ddo = {
            "@context": ["https://w3id.org/did/v1"],
            "id": did,
            "version": "4.1.0",
            "chainId": 137,  # Polygon mainnet
            "nftAddress": "",  # populated after on-chain mint
            "metadata": {
                "created": now_iso,
                "updated": now_iso,
                "type": "dataset",
                **metadata,
                "additionalInformation": {
                    "aquadome_flight_id": str(flight_id),
                    "aquadome_dataset_type": dataset_type,
                    "compute_to_data": compute_to_data,
                    "network": self._network,
                },
            },
            "services": [{
                "id": "downloadService",
                "type": "access" if not compute_to_data else "compute",
                "files": "",  # encrypted by Provider
                "datatokenAddress": "",  # populated after on-chain mint
                "serviceEndpoint": self._provider_url,
                "timeout": 0,
            }],
        }
        response = httpx.post(
            f"{self._aquarius_url}/api/aquarius/assets/ddo",
            json=ddo,
            timeout=30,
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(
                f"Aquarius DDO registration failed: {response.status_code} {response.text[:200]}"
            )
        datatoken_symbol = f"AQUA-{dataset_type.upper()[:5]}-{str(flight_id)[:4].upper()}"
        return OceanDataset(
            did=did,
            datatoken_address="",  # populated after on-chain NFT mint (requires web3.py)
            datatoken_symbol=datatoken_symbol,
            price_ocean=price_ocean,
            metadata_url=f"{self._aquarius_url}/api/aquarius/assets/ddo/{did}",
            aquadome_flight_id=flight_id,
            dataset_type=dataset_type,
        )

    def get_asset_url(self, did: str, consumer_wallet: Any) -> str:
        """
        Consumer flow: purchase 1.0 datatoken → get signed download URL.
        Fetches the DDO from Aquarius to confirm the asset exists, then
        returns the Provider access endpoint for the given DID.
        """
        response = httpx.get(
            f"{self._aquarius_url}/api/aquarius/assets/ddo/{did}",
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"Asset {did} not found in Aquarius: {response.status_code}"
            )
        return f"{self._provider_url}/api/services/download?did={did}"

    def list_published_assets(self) -> list[OceanDataset]:
        """
        Query Aquarius (Ocean metadata cache) for all assets published
        by this tenant.
        """
        response = httpx.get(
            f"{self._aquarius_url}/api/aquarius/assets/query",
            params={"q": f"aquadome_tenant_id:{self._tenant_id}", "size": 100},
            timeout=30,
        )
        if response.status_code != 200:
            logger.warning(
                "Aquarius assets/query failed: %s %s",
                response.status_code,
                response.text[:200],
            )
            return []
        hits = response.json().get("hits", {}).get("hits", [])
        return [
            OceanDataset(
                did=h["_id"],
                datatoken_address=h["_source"].get("nftAddress", ""),
                datatoken_symbol=h["_source"]["metadata"].get("name", "")[:20],
                price_ocean=1.0,
                metadata_url=f"{self._aquarius_url}/api/aquarius/assets/ddo/{h['_id']}",
            )
            for h in hits
        ]

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
