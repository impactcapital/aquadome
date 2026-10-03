"""Flight ingestion endpoints."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

router = APIRouter()


class FlightIngestResponse(BaseModel):
    flight_id: uuid.UUID
    telemetry_hash: str
    frame_count: int
    status: str


@router.post("/ingest", response_model=FlightIngestResponse)
async def ingest_flight(
    telemetry_file: UploadFile = File(...),
    pilot_cert_id: str | None = Form(default=None),
    capture_device_id: str = Form(...),
    hardware_tier: str = Form(default="commercial"),
    tenant_id: str = Form(...),
) -> FlightIngestResponse:
    """
    Accepts a drone telemetry file (DJI SRT, Skydio JSON, MAVLink .tlog),
    normalizes to MISB ST 0601 schema, computes chain-of-custody hash,
    and queues the flight for the detection/tracking/re-ID pipeline.
    """
    import tempfile
    from pathlib import Path
    from ...ingestion.normalizer import TelemetryNormalizer

    # Validate hardware tier for NDAA/ASDA compliance
    if hardware_tier not in ("commercial", "blue_uas"):
        raise HTTPException(400, "hardware_tier must be 'commercial' or 'blue_uas'")

    content = await telemetry_file.read()
    with tempfile.NamedTemporaryFile(suffix=Path(telemetry_file.filename or "").suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    normalizer = TelemetryNormalizer()
    telemetry = normalizer.normalize(tmp_path)
    telemetry.pilot_cert_id = pilot_cert_id
    telemetry.hardware_tier = hardware_tier

    return FlightIngestResponse(
        flight_id=telemetry.flight_id,
        telemetry_hash=telemetry.telemetry_hash,
        frame_count=telemetry.frame_count,
        status="queued",
    )
