# AquaDome

> *"El que no arriesga, no cruza la mar."* — One drone flight, three compliance reports, zero AGPL.

Aerial drone analytics for waterway regulatory compliance.
Developed by SustainaCities LLC / Logos Impact Foundation — Miami, FL.

## What it does

One drone flight produces **one canonical dataset**. Three statute-aligned rule engines
fan it into separate report views:

| Client | Statute | Output |
|--------|---------|--------|
| City of Miami Marine Patrol | HB 481 / FS 327.4108 | Per-vessel dwell-time compliance (green/yellow/red) |
| FWC | FWC at-risk criteria | Early-warning score + VTIP / grant pathway |
| Miami-Dade DERM | FWC trap seasons + regional closures | Trap compliance, debris, illegal dumping |

## Quick start

```bash
pip install -e ".[dev]"

# Run unit tests
pytest tests/unit/ -v

# Start API + PostGIS
docker compose -f docker/docker-compose.yml up

# Ingest a DJI SRT flight
python scripts/ingest_flight.py flight_001.SRT \
  --tenant-id marine-patrol \
  --device-id DJI-MAVIC3E-SN123 \
  --hardware-tier commercial
```

## License policy

**All core dependencies are Apache-2.0 / MIT / BSD.**
The CI pipeline (`check_licenses.py`) blocks AGPL, GPL, CC-BY-NC, and other
copyleft/non-commercial licenses from the core. See `ARCHITECTURE.md §License Policy`.

**Do NOT add:**
- Ultralytics YOLOv8/v11 (AGPL-3.0)
- OpenDroneMap/WebODM (AGPL-3.0)
- Surya OCR (GPL-3.0 + Rail-M)
- DINOv3 (custom Meta license)

## Hardware tiers (NDAA/ASDA)

| Tier | Hardware | When |
|------|----------|------|
| `commercial` | DJI, Autel | Private, non-federally-funded flights |
| `blue_uas` | DCMA Blue UAS Cleared List | Any federally-funded or government contract |

Pass `--hardware-tier=blue_uas` when flying under any federal grant or contract.

## Structure

See `ARCHITECTURE.md` for the full pipeline diagram and legal/compliance analysis.
