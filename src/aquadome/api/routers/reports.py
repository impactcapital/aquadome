"""Report generation endpoints — one canonical dataset, three client views."""

from __future__ import annotations
from fastapi import APIRouter, Query

router = APIRouter()

_VALID_REPORT_TYPES = {"marine_patrol", "fwc", "derm"}


@router.get("/{report_type}")
async def generate_report(
    report_type: str,
    tenant_id: str = Query(...),
    flight_id: str | None = Query(default=None),
    as_of: str | None = Query(default=None, description="ISO-8601 datetime"),
) -> dict:
    """
    Fan out the canonical observation dataset into a statute-specific report.

    report_type:
      marine_patrol — HB 481 / FS 327.4108 dwell-time compliance
      fwc           — At-risk / derelict vessel early-warning
      derm          — Trap compliance, debris, illegal dumping (change detection)
    """
    if report_type not in _VALID_REPORT_TYPES:
        from fastapi import HTTPException
        raise HTTPException(400, f"report_type must be one of {_VALID_REPORT_TYPES}")

    return {
        "report_type": report_type,
        "tenant_id": tenant_id,
        "flight_id": flight_id,
        "as_of": as_of,
        "status": "not_implemented",
    }
