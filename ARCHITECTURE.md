# Project AquaDome — Architecture

> **Working name:** AquaDome (may be renamed AkuaDome)
> **Owner:** SustainaCities LLC / Logos Impact Foundation — Miami, FL
> **Design principle:** One drone flight → ONE canonical processed dataset → THREE client-specific report views

## Overview

AquaDome is an aerial-drone analytics platform for waterway regulatory compliance.
A single flight produces one canonical dataset; three statute-aligned rule engines fan
it into separate report views for:

- **City of Miami Marine Patrol** — anchoring dwell-time (HB 481 / FS 327.4108)
- **FWC** — at-risk / derelict vessel early warning
- **Miami-Dade DERM** — trap compliance, debris, illegal dumping (change detection)

## License Policy (enforced in CI)

**All core dependencies MUST be Apache-2.0 / MIT / BSD.**

| Allowed | Blocked (require legal review or paid license) |
|---------|------------------------------------------------|
| RF-DETR (Apache-2.0) | Ultralytics YOLOv8/v11 (AGPL-3.0) |
| RT-DETR (Apache-2.0) | OpenDroneMap/WebODM (AGPL-3.0) |
| YOLOX (Apache-2.0) | Surya OCR (GPL-3.0 + restrictive model license) |
| SAM / SAM 2 (Apache-2.0) | DINOv3 (custom Meta license) |
| Grounding DINO (Apache-2.0) | NVIDIA RADIO-NC (non-commercial) |
| FastReID (Apache-2.0) | VisDrone / DOTA datasets (research-only) |
| Torchreid (MIT) | USCG NAIS real-time feeds (restricted) |
| PaddleOCR / docTR (Apache-2.0) | |
| roboflow/trackers (Apache-2.0) | |
| GDAL / rasterio / PDAL (MIT/BSD) | |
| DINOv2 Apache-2.0 checkpoint | |

## Pipeline (batch-first, edge later)

```
[Drone: DJI / Skydio / Blue UAS]
        │  (SRT/XMP, MAVLink, Cloud API)
        ▼
[Ingestion & MISB ST 0601 normalization]  → FlightTelemetry (SHA-256 hashed)
        ▼
[Orthorectification]  (GDAL/rasterio/PDAL; commercial engine for SaaS product)
        ▼
[Detection]  RF-DETR  →  altitude-aware tiling for small objects
        ▼
[Tracking]  BoT-SORT (roboflow/trackers)
        ▼
[Cross-flight Re-ID]  FastReID embeddings + PaddleOCR (FL hull #) + geo-proximity
        ▼
[Entity resolution & persistence]  PostGIS + GeoParquet + STAC catalog
        ▼
[Rule Engines]  Marine Patrol │ FWC at-risk │ DERM change-detection
        ▼
[Report generation]  per-tenant, row-level isolated
```

## Directory Map

```
aquadome/
├── src/aquadome/
│   ├── ontology/          # Canonical data models (Observation, Entity)
│   ├── ingestion/         # MISB ST 0601 normalization, drone adapters
│   ├── geospatial/        # GDAL/rasterio orthorectification, STAC catalog
│   ├── detection/         # RF-DETR / RT-DETR wrappers, altitude-aware tiling
│   ├── tracking/          # BoT-SORT via roboflow/trackers
│   ├── reid/              # FastReID / DINOv2 vessel re-identification
│   ├── ocr/               # PaddleOCR FL hull number extraction
│   ├── entity_resolution/ # Cross-flight entity persistence (PostGIS)
│   ├── rule_engines/
│   │   ├── marine_patrol/ # HB 481 / FS 327.4108 dwell-time engine
│   │   ├── fwc/           # At-risk criteria scorer
│   │   └── derm/          # Change detection, trap compliance
│   ├── reporting/         # Three client report views
│   ├── provenance/        # Chain-of-custody, evidentiary hashing
│   └── api/               # FastAPI service, multi-tenant routing
├── migrations/            # Alembic DB migrations
├── tests/
│   ├── unit/
│   └── integration/
├── docker/
└── scripts/               # CLI: ingest_flight, seed_gis_layers
```

## Key Legal Landmines

| Risk | Mitigation |
|------|-----------|
| AGPL contamination | CI license scanner blocks AGPL/GPL in core |
| NDAA/ASDA drone bans | Two-track hardware: DJI for private; Blue UAS for federal contracts |
| FAA BVLOS (Part 108 NPRM, not final) | All BVLOS ops require Part 107.31 waiver until rule finalizes |
| FBI CJIS Security Policy (v6.1 / audit baseline v5.9.5) | Analytics tier never ingests CJI; deliver flags across a boundary |
| Fourth Amendment (liveaboards) | Aggregate metrics; minimization/retention policy; no dwelling-interior detail |
| FL Sunshine Law Ch. 119 | Government-tenant data segregated from proprietary model IP |

## Phases

| Phase | Timeline | Goal |
|-------|----------|------|
| 0 — Governance | Weeks 0–2 | License policy in CI; CJIS-scoping legal review |
| 1 — Batch MVP | Months 1–4 | Full pipeline; Marine Patrol dwell-time engine |
| 2 — Government readiness | Months 4–9 | FIPS 140-3, CJIS Security Addendum, CoC |
| 3 — Edge / scale | Month 9+ | Jetson Orin + TensorRT (only when paid real-time use case exists) |

## Competitive Moat

Detection is a commodity. The defensible IP is:
1. **Canonical maritime entity-resolution ontology**
2. **Persistent vessel re-ID across flights without AIS**
3. **Defensible chain-of-custody / provenance** for enforcement
4. **Three statute-aligned rule engines** (no incumbent owns automated waterway compliance reporting as government SaaS)
