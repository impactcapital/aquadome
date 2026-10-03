"""Skydio Cloud API / X10 telemetry adapter (stub)."""

from __future__ import annotations

import uuid
from pathlib import Path

from ..normalizer import FlightTelemetry
from ..telemetry import KLVFrame


class SkydioAdapter:
    """
    Parses Skydio Cloud API flight log exports (JSON).

    Skydio X10 is a Blue UAS-cleared platform, making it suitable for
    federally-funded government contracts (NDAA/ASDA compliant).
    """

    def can_handle(self, source_path: Path) -> bool:
        return source_path.suffix.lower() == ".json" and "skydio" in source_path.stem.lower()

    def parse(self, source_path: Path) -> FlightTelemetry:
        import json
        from datetime import datetime, timezone

        data = json.loads(source_path.read_text())
        frames: list[KLVFrame] = []

        from ..telemetry import SensorAttitude

        for entry in data.get("telemetry", []):
            frames.append(
                KLVFrame(
                    pts_timestamp_us=int(entry.get("timestamp_us", 0)),
                    capture_datetime_utc=datetime.fromisoformat(
                        entry.get("datetime_utc", datetime.now(timezone.utc).isoformat())
                    ),
                    sensor_lat=float(entry.get("lat", 0)),
                    sensor_lon=float(entry.get("lon", 0)),
                    sensor_alt_m=float(entry.get("alt_m", 0)),
                    attitude=SensorAttitude(
                        yaw_deg=float(entry.get("yaw_deg", 0)),
                        pitch_deg=float(entry.get("pitch_deg", 0)),
                        roll_deg=float(entry.get("roll_deg", 0)),
                    ),
                    platform_designation="Skydio X10",
                )
            )

        if not frames:
            raise ValueError(f"No Skydio telemetry frames in {source_path}")

        return FlightTelemetry(
            flight_id=uuid.uuid4(),
            capture_device_id=data.get("serial_number", source_path.stem),
            platform_model="Skydio X10",
            hardware_tier="blue_uas",
            start_datetime_utc=frames[0].capture_datetime_utc,
            end_datetime_utc=frames[-1].capture_datetime_utc,
            frames=frames,
        )
