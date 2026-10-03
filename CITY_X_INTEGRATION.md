# City-X.ai — City Intelligence Tech Stack
## Esri Partnership Roadmap + MiamiVerse Integration Architecture

> *"La ciudad que no se puede medir, no se puede mejorar."* — If you can't see it in 3D with compliance data attached, you can't govern it.

---

## Brand Architecture

```
City-X.ai                          ← umbrella brand (domain available — claim it)
  │
  ├── AquaDome                     ← waterway compliance product (this repo)
  ├── [CityX-Mobility]             ← future: transit + bike/scooter corridors
  ├── [CityX-Energy]               ← future: smart grid + EV charging
  ├── [CityX-Housing]              ← future: Propy + zoning + permits
  └── [CityX-Emergency]            ← future: FEMA BCASE + OEM dashboard
         │
         └── All products share:
               SustainaCities DataHub (STAC 1.0 catalog — our platform)
               MiamiVerse viewer (CesiumJS 3D Tiles)
               AquaDome Aggregator (data backbone)
```

**Immediate action**: Register `city-x.ai` — domain appears unclaimed as of Sep 2026.

---

## Esri Partnership Roadmap

### Confirmed Facts (Esri Partner Network)

| Tier | Eligibility | Cost | Marketplace Access |
|------|-------------|------|-------------------|
| **Startup** | < 5 years old, < $2M ARR | Reduced | Yes — ArcGIS Marketplace listing |
| **Member** | Any size, demonstrated ArcGIS commitment | Standard | Yes |
| **Gold** | Higher volume / certified staff | Higher | Yes + co-marketing |
| **Platinum** | Large enterprise | Enterprise | Yes + dedicated support |

All tiers require: valid business entity, website, physical address, annual review.

**AquaDome recommended path**: Apply for **Startup tier** (if SustainaCities LLC < 5 years and < $2M ARR) or Member tier. Both unlock ArcGIS Marketplace listing.

### What Listing Unlocks

| Capability | Without EPN | With EPN (Startup+) |
|------------|-------------|---------------------|
| ArcGIS Marketplace listing | ✗ | ✓ (staff-reviewed) |
| ArcGIS Online Feature Service publishing | Via API (any) | ✓ + co-marketing |
| Esri co-marketing ("Esri Partner" badge) | ✗ | ✓ |
| Esri technical support channel | ✗ | ✓ |
| Access to Partner Community portal | ✗ | ✓ (OAuth + ArcGIS Identity specs) |
| Government/enterprise introductions | ✗ | High probability |

### Marketplace Listing Types for AquaDome

| Listing | Type | Price Model |
|---------|------|-------------|
| AquaDome Waterway Compliance Layer | **Data** | $50–200/seat/mo |
| AquaDome AGOL Dashboard Template | **App (Widget)** | Free (drives subscriptions) |
| City-X.ai MiamiVerse Integration | **Solution** | Custom enterprise |

### Spexi's Position vs. AquaDome's Path

| | Spexi | AquaDome (City-X.ai) |
|-|-------|----------------------|
| Esri relationship | Listed as "Spexi for Government" solution | Apply Startup → Member |
| Integration depth | GeoJSON file exports (manual import) | **Hosted Feature Services** (queryable, live) |
| Compliance attributes | None | dwell_stat, at_risk, trap_stat (statute-aligned) |
| ArcGIS Marketplace | Imagery data listing | Compliance intelligence listing |

**Competitive move**: Position AquaDome as "Esri Compliance Intelligence Partner" — the compliance layer that makes Spexi's imagery actionable for government enforcement.

---

## MiamiVerse Integration Architecture (City-X.ai Full Stack)

```
City-X.ai Data Backbone
────────────────────────────────────────────────────────────────────
External Sources                AquaDome Processing
─────────────────               ──────────────────
Spexi (raw imagery)  ──────►    RF-DETR detection
dClimate (weather)   ──────►    BoT-SORT tracking          ──►  Entity records
NOAA AIS (vessels)   ──────►    FastReID re-ID                   (PostGIS)
FEMA (damage)        ──────►    PaddleOCR hull #                    │
                                Rule engines                         │
                                (Marine Patrol, FWC, DERM)           │
                                                                      ▼
                            ┌─────────────────────────────────────────┐
                            │   SustainaCities DataHub (our platform)  │
                            │   STAC 1.0 catalog — canonical truth     │
                            │   https://sustainacities.com/stac        │
                            └────────────────┬────────────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
             ArcGIS Online            Ocean Protocol           dClimate
         Hosted Feature Service    ERC20 datatokens          Polygon+IPFS
         (Esri Partner listing)    (Compute-to-Data)         (3 series)
         Miami GIS staff query     AI labs / insurers        Climate context
         compliance maps directly  pay per-query             subscribers
                    │                        │                        │
                    └────────────────────────┴────────────────────────┘
                                             │
                                             ▼
                            ┌─────────────────────────────────────────┐
                            │              MiamiVerse                  │
                            │   CesiumJS 3D viewer + AR companion      │
                            │   Layers:                                │
                            │   • AquaDome compliance overlay (colored)│
                            │   • Spexi base imagery (3D Tiles/3DGS)  │
                            │   • dClimate weather context             │
                            │   • Niantic VPS AR anchors               │
                            │   • [Future City-X.ai: mobility, energy] │
                            └─────────────────────────────────────────┘
```

---

## Esri Integration — Technical Implementation

### Step 1: ArcGIS Identity (OAuth 2.0)

Required for all ArcGIS Online API calls. Wire `marketplace/arcgis_online.py`:
```python
# Already stubbed in arcgis_online.py:
publisher.get_token()
# POST https://{org}.maps.arcgis.com/sharing/rest/oauth2/token
# grant_type=client_credentials&client_id=...&client_secret=...
```

### Step 2: Hosted Feature Service

AquaDome publishes compliance entities as a hosted Feature Service — not a static GeoJSON file. This is the key differentiator from Spexi:

```
GET https://services.arcgis.com/{org}/arcgis/rest/services/AquaDome_Miami_Waterway/FeatureServer/0/query
  ?where=dwell_stat='red' AND at_risk_n>=3
  &outFields=entity_id,fl_reg_num,lat,lon,dwell_stat,at_risk
  &f=geojson
```

Government GIS analysts query live compliance data directly in ArcGIS Pro without downloading anything.

### Step 3: ArcGIS Dashboard Template

Publish a free ArcGIS Dashboard template that connects to the AquaDome Feature Service. Cities apply the template to their AGOL subscription → instant compliance dashboard. This drives subscriptions at zero incremental cost.

Dashboard widgets:
- Compliance heat map (RED/YELLOW/GREEN vessel density)
- Monthly dwell-time trend chart
- At-risk vessel count (FWC tier breakdown)
- DERM trap compliance table
- Change-detection alert feed (new debris events)

### Step 4: Marketplace Listing Application

1. Join EPN Startup tier at https://www.esri.com/en-us/about/partners/become-partner
2. Sign into Esri Partner Community → submit "Become a Provider" workflow
3. List two items:
   - **Data**: "AquaDome Miami Waterway Compliance Layer" ($50–200/seat/mo)
   - **App**: "AquaDome AGOL Dashboard Template" (Free)
4. Annual provider review — maintain by keeping Feature Service live + documentation current

---

## City-X.ai Esri Co-Marketing Positioning

```
"City-X.ai: Compliance Intelligence for Smart Cities"

Built on ArcGIS — bringing statute-aligned regulatory intelligence
to every city's GIS infrastructure.

Products:
  AquaDome       → waterway compliance (HB 481, FWC, DERM)
  [CityX-Mobile] → mobility + transit compliance
  [CityX-Energy] → grid compliance + EV infrastructure

Every City-X.ai product publishes to:
  ✓ SustainaCities DataHub (canonical)
  ✓ ArcGIS Marketplace (government distribution)
  ✓ MiamiVerse (citizen-facing 3D intelligence)
  ✓ Ocean Protocol (decentralized research/insurance market)
  ✓ dClimate (environmental data marketplace)
```

---

## MiamiVerse Layer Catalog (City-X.ai Contribution)

| Layer | Source | Update Frequency | Status |
|-------|--------|-----------------|--------|
| Vessel dwell compliance | AquaDome | Per flight (~weekly) | Code complete |
| Trap compliance | AquaDome | Per flight | Code complete |
| Debris change detection | AquaDome | Per flight pair | Code complete |
| Base waterway 3D scene | Spexi → Cesium ion | Per capture | Code complete (spatial/) |
| Weather/storm context | dClimate | Daily | Code complete (dclimate.py) |
| NOAA AIS vessel traffic | NOAA MarineCadastre | Daily | Stubbed (aggregator.py) |
| AR compliance anchors | Niantic VPS | Per flight | Architecture complete |
| [Future] Transit corridors | City-X.ai Mobility | Real-time | Planned |
| [Future] Energy grid | City-X.ai Energy | Real-time | Planned |

---

## Action Items

| Priority | Action | Owner | Timeline |
|----------|--------|-------|----------|
| 🔴 Now | Register `city-x.ai` domain | Silvio | This week |
| 🔴 Now | Apply EPN Startup tier | SustainaCities LLC | 2 weeks |
| 🟡 Phase 1 | Wire `arcgis_online.py` → AGOL API (OAuth + Feature Service) | Dev | Month 1 |
| 🟡 Phase 1 | Close Marine Patrol + FWC government contracts | Silvio | Month 1–2 |
| 🟡 Phase 1 | Register `aquadome.waterway.dwell.miami` on dClimate | Dev | Month 1 |
| 🟡 Phase 1 | Publish first Ocean Protocol datatoken (dwell GeoParquet) | Dev | Month 2 |
| 🟢 Phase 2 | Submit ArcGIS Marketplace listing (data + dashboard template) | Dev + Silvio | Month 3 |
| 🟢 Phase 2 | Wire `aggregator.py` → full pipeline (Celery task) | Dev | Month 2–3 |
| 🟢 Phase 2 | MiamiVerse partnership — DataHub STAC webhook integration | Silvio | Month 3–4 |
| 🔵 Phase 3 | Esri co-marketing campaign ("Compliance Intelligence for Smart Cities") | Silvio | Month 6 |
| 🔵 Phase 3 | City-X.ai Mobility product scoping | Silvio | Month 6–12 |
