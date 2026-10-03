"""MAVLink (ArduPilot / PX4) telemetry adapter (stub)."""

from __future__ import annotations

import uuid
from pathlib import Path

from ..normalizer import FlightTelemetry


class MAVLinkAdapter:
    """
    Parses MAVLink .tlog or .bin flight logs.
    Supports ArduPilot and PX4 autopilots — common on Blue UAS custom builds.
    """

    def can_handle(self, source_path: Path) -> bool:
        return source_path.suffix.lower() in (".tlog", ".bin")

    def parse(self, source_path: Path) -> FlightTelemetry:
        # Full implementation requires pymavlink (Apache-2.0):
        #   pip install pymavlink
        # Stub returns minimal structure; wire in pymavlink.mavutil for production.
        from datetime import datetime, timezone

        return FlightTelemetry(
            flight_id=uuid.uuid4(),
            capture_device_id=source_path.stem,
            platform_model="MAVLink-autopilot",
            hardware_tier="blue_uas",
            start_datetime_utc=datetime.now(timezone.utc),
            frames=[],
        )
