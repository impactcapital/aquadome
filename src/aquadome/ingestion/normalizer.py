"""
Telemetry normalizer — converts raw drone formats to canonical FlightTelemetry.

Supported adapters: DJI SRT/XMP, Skydio Cloud API, MAVLink (ArduPilot/PX4).
All sources converge to the same FlightTelemetry schema keyed on frame PTS
timestamps and hashed for chain-of-custody per MISB ST 0601.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel

from .telemetry import KLVFrame


class FlightTelemetry(BaseModel):
    """Canonical normalized telemetry for one drone flight."""

    flight_id: uuid.UUID = uuid.uuid4()
    pilot_cert_id: str | None = None
    capture_device_id: str               # drone serial or MAC
    hardware_tier: str = "commercial"    # "commercial" | "blue_uas"
    platform_model: str                  # e.g. "DJI Mavic 3E"
    start_datetime_utc: datetime
    end_datetime_utc: datetime | None = None

    frames: list[KLVFrame]

    # Chain-of-custody: SHA-256 over the full ordered frame sequence
    telemetry_hash: str = ""

    def compute_hash(self) -> str:
        payload = json.dumps(
            [f.to_canonical_dict() for f in self.frames], sort_keys=True
        ).encode()
        self.telemetry_hash = hashlib.sha256(payload).hexdigest()
        return self.telemetry_hash

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def duration_seconds(self) -> float | None:
        if self.end_datetime_utc is None:
            return None
        return (self.end_datetime_utc - self.start_datetime_utc).total_seconds()


class DroneAdapter(Protocol):
    """Protocol every drone-platform adapter must satisfy."""

    def can_handle(self, source_path: Path) -> bool: ...

    def parse(self, source_path: Path) -> FlightTelemetry: ...


class TelemetryNormalizer:
    """
    Selects the appropriate adapter and returns a canonical FlightTelemetry.

    Usage:
        normalizer = TelemetryNormalizer()
        telemetry = normalizer.normalize(Path("flight_001.SRT"))
    """

    def __init__(self) -> None:
        from .adapters.dji import DJISRTAdapter
        from .adapters.skydio import SkydioAdapter
        from .adapters.mavlink import MAVLinkAdapter

        self._adapters: list[DroneAdapter] = [
            DJISRTAdapter(),
            SkydioAdapter(),
            MAVLinkAdapter(),
        ]

    def normalize(self, source_path: Path, **kwargs) -> FlightTelemetry:
        for adapter in self._adapters:
            if adapter.can_handle(source_path):
                telemetry = adapter.parse(source_path)
                telemetry.compute_hash()
                return telemetry
        raise ValueError(f"No adapter can handle: {source_path}")
