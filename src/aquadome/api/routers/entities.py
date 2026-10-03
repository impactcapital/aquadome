"""Entity query endpoints — vessels, traps, debris items."""

from __future__ import annotations
import uuid
from fastapi import APIRouter, Query

router = APIRouter()


@router.get("/{entity_id}")
async def get_entity(entity_id: uuid.UUID, tenant_id: str = Query(...)) -> dict:
    """Fetch a persistent entity by ID (tenant-scoped)."""
    return {"entity_id": str(entity_id), "tenant_id": tenant_id, "status": "not_implemented"}


@router.get("/")
async def list_entities(
    entity_type: str | None = Query(default=None),
    dwell_status: str | None = Query(default=None),
    at_risk_tier: str | None = Query(default=None),
    tenant_id: str = Query(...),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0),
) -> dict:
    """List entities with optional filtering by type, dwell status, at-risk tier."""
    return {
        "entities": [],
        "total": 0,
        "limit": limit,
        "offset": offset,
        "status": "not_implemented",
    }
