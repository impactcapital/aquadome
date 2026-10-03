"""MISB ST 0601 KLV telemetry data structures."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FrameCorners:
    """
    MISB ST 0601 Tags 26–29: frame geodetic corner offsets.
    Enables per-frame ground geolocation without an orthomosaic.
    """
    upper_left: tuple[float, float]    # (lat, lon) WGS84
    upper_right: tuple[float, float]
    lower_right: tuple[float, float]
    lower_left: tuple[float, float]


@dataclass
class SensorAttitude:
    """MISB ST 0601 Tags 18–20: platform attitude."""
    yaw_deg: float
    pitch_deg: float
    roll_deg: float


@dataclass
class KLVFrame:
    """
    One MISB ST 0601 KLV metadata frame aligned to a video PTS timestamp.
    ~200 bytes per frame at 30 FPS → ~6 kB/s.
    """
    pts_timestamp_us: int              # microseconds since epoch
    capture_datetime_utc: datetime

    # Sensor platform (Tag 13–15)
    sensor_lat: float
    sensor_lon: float
    sensor_alt_m: float

    # Sensor attitude
    attitude: SensorAttitude

    # Frame corners (Tags 26–29) — critical for ground geolocation
    frame_corners: FrameCorners | None = None

    # Slant range / field of view
    slant_range_m: float | None = None
    horizontal_fov_deg: float | None = None
    vertical_fov_deg: float | None = None

    # Platform metadata
    platform_designation: str = ""     # drone model
    sensor_model: str = ""             # camera model

    # Extra raw KLV tags for forward-compatibility
    raw_tags: dict[int, bytes] = field(default_factory=dict)

    def to_canonical_dict(self) -> dict:
        return {
            "pts_timestamp_us": self.pts_timestamp_us,
            "capture_datetime_utc": self.capture_datetime_utc.isoformat(),
            "sensor_lat": self.sensor_lat,
            "sensor_lon": self.sensor_lon,
            "sensor_alt_m": self.sensor_alt_m,
            "attitude_yaw": self.attitude.yaw_deg,
            "attitude_pitch": self.attitude.pitch_deg,
            "attitude_roll": self.attitude.roll_deg,
            "frame_corners": (
                {
                    "ul": self.frame_corners.upper_left,
                    "ur": self.frame_corners.upper_right,
                    "lr": self.frame_corners.lower_right,
                    "ll": self.frame_corners.lower_left,
                }
                if self.frame_corners
                else None
            ),
        }

    def sha256_hash(self) -> str:
        payload = json.dumps(self.to_canonical_dict(), sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()
