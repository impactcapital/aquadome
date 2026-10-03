# AkuaDome Spatial Pipeline — Drone → 3DGS → Data Marketplace → MiamiVerse

> *"No hay mapa sin territorio."* — The data marketplace is only as good as the ground truth it captures.

## Overview

One AkuaDome flight produces two parallel outputs:

| Track | Output | Consumer |
|-------|--------|----------|
| **Compliance** | Observation → Entity → Rule-engine reports | Marine Patrol, FWC, DERM |
| **Spatial** | Orthomosaic → 3D Gaussian Splat → Tagged 3D Tileset | SustainaCities DataHub, MiamiVerse |

The spatial track turns every flight into a living, searchable 3D layer of Miami's waterways — vessels flagged RED by the dwell-time engine appear as annotated pins in MiamiVerse the same day the flight lands.

---

## Pipeline Architecture

```
Drone capture (DJI Mavic 3E / Blue UAS)
         │
         ▼
  AkuaDome Ingestion
  (MISB ST 0601 KLV, SHA-256 telemetry hash)
         │
         ├──────────────────────────────► Compliance track
         │                               (RF-DETR → BoT-SORT → FastReID
         │                                → Rule engines → PostGIS)
         ▼
  Raw imagery frames + georeferenced GCPs
         │
         ├── Option A ──► Spexi Geospatial Upload API
         │                (OGC API-Features; pilot network route)
         │                       │
         │                       ▼
         │               Niantic Spatial Reconstruction API
         │               (city-scale georeferenced 3DGS)
         │                       │
         │                       ▼
         │               Niantic VPS Map (NSDK 4.0)
         │               + glTF / KHR_gaussian_splatting asset
         │
         ├── Option B ──► Cesium ion REST API (direct upload)
         │                (drone photos → 3D Tileset mesh + Gaussian splat)
         │                (Apache-2.0 CesiumJS; 3D Tiles 2.0 / OGC standard)
         │
         └── Option C ──► Luma Labs Capture API
                          (lumalabs.ai/api; fastest per-scene reconstruction)
                          (output: NeRF / 3DGS downloadable asset)
                          ⚠ Check commercial license terms before production use

         All paths converge:
         ▼
  Georeferenced 3D Tileset (3D Tiles 2.0 + KHR_gaussian_splatting)
         │
  AkuaDome Spatial Tagger
  (attaches AkuaDome entity properties as 3D Tiles feature metadata)
         │
         ├──► SustainaCities DataHub
         │    (STAC Item → GeoParquet catalog → Data marketplace listing)
         │    Format: STAC 1.0 + eo/sar/label extensions
         │
         └──► MiamiVerse / CesiumJS viewer
              (3D Tiles layer; compliance-flagged vessels = colored billboards)
              AR companion app (miamiverse.world)
```

---

## Integration Points

### 1. Spexi Geospatial ("the Plexi")

**What it is**: 10,000+ licensed drone pilot network; 6M+ acres at 2.8 cm/px resolution (May 2026 partnership with Niantic Spatial routes captures through Niantic Reconstruction API). Formerly SpexiGeo; now integrates with LayerDrone Network.

**API standard**: OGC API-Features (GeoJSON + GeoParquet output)

**Docs**: https://docs.spexi.com

**AkuaDome integration**:
- `aquadome/src/aquadome/spatial/spexi.py` — `SpexiClient`
- On flight completion, `SpexiClient.upload_flight()` posts imagery + GCPs to Spexi's API
- Spexi returns a `capture_id`; poll `SpexiClient.get_reconstruction_status()` until complete
- On completion, download the 3DGS asset URL and hand it to `CesiumIonUploader`

**When to use**: When flights are flown by Spexi network pilots (city-contracted coverage, emergency response mapping, regional surveys). Spexi handles FAA compliance, insurance, and pilot dispatch.

### 2. Niantic Spatial Reconstruction API

**What it is**: Large geospatial model; NSDK 4.0 (Unity / Swift / Android / ROS2). Scaniverse generates VPS maps, meshes, Gaussian Splats from drone captures.

**Output**: `KHR_gaussian_splatting` glTF asset + Niantic VPS map (enables AR anchoring in the Scaniverse / 8th Wall / MiamiVerse AR companion)

**AkuaDome integration**: Indirect — Spexi's API automatically routes to Niantic Reconstruction API as of May 2026. For direct API access, contact Niantic Spatial enterprise.

### 3. Cesium ion

**What it is**: End-to-end drone photos → georeferenced 3D Tileset (mesh, point cloud, or Gaussian splats). Now an OGC standard (3D Tiles 2.0). Apache-2.0 CesiumJS.

**REST API**: `POST /v1/assets` to create an asset, `POST /v1/assets/{id}/uploadFiles` to upload imagery, then GET to poll tiling status.

**AkuaDome integration**:
- `aquadome/src/aquadome/spatial/cesium_ion.py` — `CesiumIonUploader`
- Takes flight imagery directory + GCPs → Cesium ion tileset asset ID
- Tileset URL is stored as `orthomosaic_id` on Observations (STAC item ID convention)

**Why preferred for MiamiVerse**: CesiumJS is the de-facto renderer for geospatial digital twins. MiamiVerse almost certainly runs CesiumJS or a CesiumJS-compatible viewer.

### 4. AkuaDome Spatial Tagger

This is new code we add to AkuaDome (`spatial/tiles3d_tagger.py`). After any 3D Tileset is generated, the tagger:

1. Queries AkuaDome's PostGIS for all Entity records whose `canonical_geometry` falls within the tileset's bounding box
2. For each Entity, constructs a GeoJSON Feature with AkuaDome compliance properties (dwell_status, at_risk_tier, trap_legal_status, etc.)
3. Writes these as a `3DTILES_metadata` batch table schema on the tileset root
4. Outputs an overlay GeoJSON + STAC label extension for the DataHub listing

### 5. SustainaCities DataHub

**Format**: STAC 1.0 Item with extensions:
- `eo` (electro-optical sensor metadata)
- `label` (compliance annotations per entity)
- `aquadome:` custom extension namespace

**AkuaDome integration**:
- `aquadome/src/aquadome/spatial/stac_catalog.py` — `STACCatalogBuilder`
- Produces a STAC Item JSON pointing to:
  - The Cesium ion tileset URL (asset link)
  - The GeoParquet entity table (data link)
  - The compliance report PDF (derived link)

### 6. MiamiVerse

**What it is**: Miami's Digital Twin Platform — CesiumJS-based 3D viewer + AR companion. Public-private-academic collaboration with SustainaCities, Magma DTT®, Propy, Akila, Filecoin (miamiverse.world).

**AkuaDome integration**: No custom SDK needed. Publish the Cesium ion tileset URL + the entity GeoJSON overlay to the SustainaCities DataHub. MiamiVerse ingests georeferenced 3D Tiles layers from the DataHub catalog.

For the AR companion layer (Scaniverse / 8th Wall-based): request a Niantic VPS map ID from Spexi/Niantic for each survey area. This enables Scaniverse AR anchoring so field officers can walk the marina and see compliance overlays in AR.

---

## Data Formats Reference

| Asset | Format | Standard |
|-------|--------|----------|
| Tileset | 3D Tiles 2.0 + KHR_gaussian_splatting | OGC / Khronos |
| Splat asset | glTF 2.0 + KHR_gaussian_splatting | Khronos |
| Geospatial catalog | STAC 1.0 Item | Radiant Earth |
| Entity table | GeoParquet 1.1 | OGC |
| Compliance overlay | GeoJSON + 3DTILES_metadata | OGC |
| AR anchor | Niantic VPS Map | Niantic NSDK 4.0 |
| Imagery metadata | MISB ST 0601 KLV | STANAG 4609 |

---

## Reconstruction Backend Decision Tree

```
Is the flight commercially sensitive / law-enforcement adjacent?
    YES → Cesium ion (enterprise, SOC 2) or self-hosted via GDAL/rasterio
    NO  → Continue

Is the area already in Spexi's coverage network?
    YES → Spexi Upload API → Niantic Reconstruction (best georeferencing + VPS)
    NO  → Continue

Need fastest turnaround for emergency response?
    YES → Luma Labs API (check commercial terms; fastest per-scene)
    NO  → Cesium ion direct upload (best MiamiVerse / CesiumJS integration)
```

---

## Licensing Notes

| Service | License / Terms |
|---------|----------------|
| Spexi Geospatial API | Commercial SaaS; check enterprise tier |
| Niantic Spatial SDK | NSDK 4.0 commercial license |
| Cesium ion | SaaS; CesiumJS renderer is Apache-2.0 |
| Luma Labs API | Commercial SaaS — verify terms before production |
| GDAL / rasterio | MIT / BSD — safe for self-hosted orthorectification |
| 3D Tiles 2.0 spec | OGC open standard |
| KHR_gaussian_splatting | Khronos open extension |

**Self-hosted orthorectification**: Use GDAL + rasterio + PDAL (all MIT/BSD). Do NOT use ODM/WebODM (AGPL-3.0) in the served SaaS core — see ARCHITECTURE.md §License Policy.

---

## Emergency Management Use Case

For Miami-Dade OEM / FEMA Section 428 response:

1. Dispatch a Spexi pilot (or Blue UAS flight) over an impacted area
2. AkuaDome ingestion runs in under 30 minutes post-flight
3. Cesium ion reconstruction produces a 3D Tileset in ~60 minutes
4. The Spatial Tagger annotates debris change-detection events from the DERM engine
5. The STAC Item lands in the SustainaCities DataHub with a `disaster_response: true` tag
6. MiamiVerse OEM dashboard shows the updated layer; field teams see AR overlays via Scaniverse

This flow maps directly onto FEMA's BCASE (Building Capture and Site Evaluation) workflow and can feed FEMA's Geospatial Resource Center (GRC) via STAC API.
