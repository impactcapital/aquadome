"""
DJI SRT / XMP telemetry adapter.

DJI SRT format carries GPS position, altitude, gimbal attitude, and timestamps
per frame. This adapter parses DJI SRT files and maps them to canonical KLVFrame
records (MISB ST 0601 schema) for chain-of-custody hashing.

For government contracts, SRT can be transcoded to true KLV streams via
tools such as ImpleoTV KlvInjector; this adapter handles the pre-transcode path.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ..normalizer import FlightTelemetry
from ..telemetry import FrameCorners, KLVFrame, SensorAttitude

# DJI SRT block pattern (varies by firmware version)
_BLOCK_PATTERN = re.compile(
    r"(?P<seq>\d+)\r?\n"
    r"(?P<start_tc>[\d:,]+) --> (?P<end_tc>[\d:,]+)\r?\n"
    r"(?P<payload>.*?)\r?\n\r?\n",
    re.DOTALL,
)

_GPS_PATTERN = re.compile(
    r"\[latitude: (?P<lat>[-\d.]+)\] \[longitude: (?P<lon>[-\d.]+)\]"
    r".*?\[altitude: (?P<alt>[-\d.]+)\]",
    re.DOTALL,
)

_GIMBAL_PATTERN = re.compile(
    r"\[gimbal_pitch: (?P<pitch>[-\d.]+)\]"
    r".*?\[gimbal_roll: (?P<roll>[-\d.]+)\]"
    r".*?\[gimbal_yaw: (?P<yaw>[-\d.]+)\]",
    re.DOTALL,
)


class DJISRTAdapter:
    def can_handle(self, source_path: Path) -> bool:
        return source_path.suffix.lower() in (".srt", ".xmp")

    def parse(self, source_path: Path) -> FlightTelemetry:
        raw = source_path.read_text(encoding="utf-8", errors="replace")
        frames: list[KLVFrame] = []

        for match in _BLOCK_PATTERN.finditer(raw):
            payload = match.group("payload")
            gps = _GPS_PATTERN.search(payload)
            gimbal = _GIMBAL_PATTERN.search(payload)

            if not gps:
                continue

            lat = float(gps.group("lat"))
            lon = float(gps.group("lon"))
            alt = float(gps.group("alt"))

            yaw = float(gimbal.group("yaw")) if gimbal else 0.0
            pitch = float(gimbal.group("pitch")) if gimbal else 0.0
            roll = float(gimbal.group("roll")) if gimbal else 0.0

            # Derive PTS from sequence number (approximate — real impl uses SRT timecodes)
            seq = int(match.group("seq"))
            pts_us = seq * 33_333  # ~30 FPS placeholder

            frames.append(
                KLVFrame(
                    pts_timestamp_us=pts_us,
                    capture_datetime_utc=datetime.now(timezone.utc),
                    sensor_lat=lat,
                    sensor_lon=lon,
                    sensor_alt_m=alt,
                    attitude=SensorAttitude(yaw_deg=yaw, pitch_deg=pitch, roll_deg=roll),
                    platform_designation="DJI",
                )
            )

        if not frames:
            raise ValueError(f"No parseable DJI SRT frames found in {source_path}")

        start = frames[0].capture_datetime_utc
        end = frames[-1].capture_datetime_utc

        return FlightTelemetry(
            flight_id=uuid.uuid4(),
            capture_device_id=source_path.stem,
            platform_model="DJI",
            start_datetime_utc=start,
            end_datetime_utc=end,
            frames=frames,
        )
