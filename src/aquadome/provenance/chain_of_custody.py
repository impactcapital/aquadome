"""
Chain-of-Custody for AquaDome observations.

Enforcement-grade observations require a defensible audit trail:
  - SHA-256 hash of the MISB ST 0601 KLV telemetry block (per-flight)
  - SHA-256 hash of each Observation record (immutable after creation)
  - Reviewer identity and timestamp for human-confirmed records

ISO 19115 metadata alignment: lineage / source fields.
NIEM alignment: chain-of-custody / evidence fields for law-enforcement exchange.

CJIS note: raw imagery and dwell-time analytics are NOT CJI by themselves.
CJIS scope attaches only when commingled with PII in a criminal-justice context,
case/incident records, NCIC hits, or biometrics. Architecture keeps AquaDome
analytics tier out of CJI scope — deliver flags across a boundary.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from ..ontology.models import Observation


@dataclass
class ProvenanceRecord:
    """Immutable provenance record attached to a confirmed observation."""
    observation_id: uuid.UUID
    observation_hash: str       # SHA-256 of the canonical Observation JSON
    telemetry_hash: str         # SHA-256 of the FlightTelemetry KLV block
    pipeline_run_id: uuid.UUID
    capture_device_id: str
    pilot_cert_id: str | None
    created_at: datetime
    reviewer_id: str | None = None
    review_datetime: datetime | None = None
    is_confirmed: bool = False


def sign_observation(obs: Observation) -> ProvenanceRecord:
    """
    Creates a ProvenanceRecord for an Observation.
    The observation_hash is deterministic — any mutation of obs will produce
    a different hash, making tampering detectable.
    """
    canonical = json.dumps(
        {k: str(v) for k, v in obs.model_dump().items()},
        sort_keys=True,
    ).encode()
    obs_hash = hashlib.sha256(canonical).hexdigest()

    return ProvenanceRecord(
        observation_id=obs.observation_id,
        observation_hash=obs_hash,
        telemetry_hash=obs.flight_telemetry_hash,
        pipeline_run_id=obs.pipeline_run_id,
        capture_device_id=obs.capture_device_id,
        pilot_cert_id=obs.pilot_cert_id,
        created_at=datetime.now(timezone.utc),
        reviewer_id=obs.reviewer_id,
        review_datetime=obs.review_datetime,
        is_confirmed=obs.human_review_status.value == "confirmed",
    )
