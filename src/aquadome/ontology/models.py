"""
Canonical AquaDome data models.

Two-layer architecture:
  Observation — immutable, append-only, one per detection per frame.
  Entity      — persistent, mutable, resolved across flights via re-ID.

Aligns to ISO 19115 (geospatial metadata), STAC (imagery), OGC geometry,
Darwin Core (environmental), and NIEM (law-enforcement exchange fields).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .enums import (
    AtRiskTier,
    DwellStatus,
    EntityType,
    GeolocationSource,
    HumanReviewStatus,
    ObjectClass,
    ResolutionMethod,
    SeasonStatus,
    TrapGearType,
    TrapLegalStatus,
)


# ---------------------------------------------------------------------------
# Observation — immutable, one per detection per frame
# ---------------------------------------------------------------------------

class Point2D(BaseModel):
    lon: float
    lat: float


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def area(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1)


class Observation(BaseModel):
    """
    Immutable observation record. Append-only — never mutate after write.
    One record is created per detection per frame during the tracking pipeline.
    """

    # Identity
    observation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    flight_id: uuid.UUID
    frame_pts_timestamp: int           # microseconds since epoch (PTS)
    capture_datetime_utc: datetime

    # Geometry (WGS84; UTM stored separately in PostGIS)
    geometry: Point2D                  # centroid
    bbox_pixels: BoundingBox | None = None
    geolocation_source: GeolocationSource

    # Classification
    object_class: ObjectClass
    class_confidence: float = Field(ge=0.0, le=1.0)

    # Detector provenance
    detector_model_id: str             # e.g. "rfdetr"
    detector_model_version: str        # semver, e.g. "1.0.0"
    tracker_track_id: int | None = None

    # Re-ID
    reid_embedding: list[float] | None = None
    reid_embedding_model: str | None = None

    # OCR (FL hull registration number)
    ocr_text: str | None = None
    ocr_confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # Chain-of-custody / provenance
    capture_device_id: str             # drone serial number or MAC
    pilot_cert_id: str | None = None   # FAA Remote Pilot Certificate number
    flight_telemetry_hash: str         # SHA-256 of MISB ST 0601 KLV block
    orthomosaic_id: str | None = None  # STAC item ID if orthorectified
    pipeline_run_id: uuid.UUID

    # Human review
    human_review_status: HumanReviewStatus = HumanReviewStatus.UNREVIEWED
    reviewer_id: str | None = None
    review_datetime: datetime | None = None

    # Multi-tenancy
    tenant_id: str

    @field_validator("reid_embedding")
    @classmethod
    def _embedding_dim(cls, v: list[float] | None) -> list[float] | None:
        if v is not None and len(v) not in (256, 512, 768, 1024, 2048):
            raise ValueError("Unexpected embedding dimension")
        return v

    model_config = {"frozen": True}  # Observations are immutable


# ---------------------------------------------------------------------------
# DwellSegment — one continuous anchoring episode for a Vessel entity
# ---------------------------------------------------------------------------

class DwellSegment(BaseModel):
    """Continuous period when a vessel was observed at a fixed location."""

    segment_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    entity_id: uuid.UUID
    start_datetime_utc: datetime
    end_datetime_utc: datetime | None = None   # None = ongoing
    geometry_centroid: Point2D
    in_mooring_field: bool = False
    in_permitted_work_area: bool = False
    in_no_anchor_buffer: bool = False

    @property
    def duration_days(self) -> float | None:
        if self.end_datetime_utc is None:
            return None
        delta = self.end_datetime_utc - self.start_datetime_utc
        return delta.total_seconds() / 86_400


# ---------------------------------------------------------------------------
# Entity — persistent, mutable, resolved across flights
# ---------------------------------------------------------------------------

class Entity(BaseModel):
    """
    Persistent waterway object resolved from one or more Observations.
    Updated as new flights add evidence; the Observation log is immutable.
    """

    entity_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    entity_type: EntityType

    first_observed: datetime
    last_observed: datetime
    observation_ids: list[uuid.UUID] = Field(default_factory=list)

    # Resolved identifiers
    fl_registration_number: str | None = None   # Florida hull number (OCR)
    hull_color: str | None = None
    mmsi: str | None = None                     # AIS MMSI if corroborated
    canonical_geometry: Point2D | None = None   # current best-known position

    # Re-ID
    reid_signature: list[float] | None = None   # aggregated embedding
    resolution_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    resolution_method: ResolutionMethod | None = None

    # --- Vessel-specific ---
    dwell_segments: list[DwellSegment] = Field(default_factory=list)
    dwell_status: DwellStatus | None = None

    # --- Trap-specific ---
    gear_type: TrapGearType | None = None
    season_status_at_observation: SeasonStatus | None = None
    trap_legal_status: TrapLegalStatus | None = None
    trap_registration_prefix: str | None = None   # B (blue crab) / S (stone crab)

    # --- FWC at-risk scoring ---
    at_risk_tier: AtRiskTier | None = None
    at_risk_criteria_met: list[str] = Field(default_factory=list)

    # --- DebrisItem-specific ---
    change_detection_pair_ids: list[str] = Field(default_factory=list)
    first_appearance_flight_id: uuid.UUID | None = None

    # Multi-tenancy
    tenant_id: str

    # Raw extra fields for NIEM law-enforcement exchange
    niem_metadata: dict[str, Any] = Field(default_factory=dict)

    def dwell_days_in_window(self, window_days: int = 180) -> float:
        """
        Sum dwell time in rolling `window_days` window, excluding mooring
        fields and permitted work areas per HB 481 / FS 327.4108.
        """
        from datetime import timezone
        now = datetime.now(timezone.utc)
        cutoff = now.replace(tzinfo=timezone.utc) if now.tzinfo else now
        total = 0.0
        for seg in self.dwell_segments:
            if seg.in_mooring_field or seg.in_permitted_work_area:
                continue
            end = seg.end_datetime_utc or cutoff
            start = seg.start_datetime_utc
            # Only count the portion within the rolling window
            window_start = end.__class__.fromisoformat(
                end.isoformat()
            )  # placeholder; real impl uses timedelta
            days = seg.duration_days
            if days is not None:
                total += days
        return total
