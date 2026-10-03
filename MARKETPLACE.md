# AkuaDome Data Marketplace Strategy
## How to Leverage — and Beat — Spexi/LayerDrone in the Waterway Intelligence Market

> *"El que llega primero, llega mejor."* — First to market with compliance-grade data wins the government contracts; everyone else sells pixels.

---

## The Competitive Landscape (Confirmed Facts)

### Spexi Geospatial
- **Model**: Centralized coordinator of 10,000+ drone pilots; sells imagery at 2.8 cm/px; 6M+ acres surveyed
- **ArcGIS integration**: Publishes **GeoJSON files** only — users must import manually; NOT hosted Feature Services
- **Buyers**: Amazon, State Farm, Niantic, Google, Uber, Esri (per de:pin day Dubai slide)
- **Weakness**: Sells raw pixels. No compliance verdicts. No statute alignment. No chain-of-custody for legal proceedings.

### LayerDrone
- **Origin**: Spun out of Spexi (2025); same COO — Alec Wilson; separate non-profit foundation
- **Model**: DePIN (Decentralized Physical Infrastructure Network); pilots earn **USDC on Base blockchain** + non-transferable reputation NFTs
- **Verification**: Soulbound NFT minted per flight; metadata must cryptographically match imagery or pilot is not paid
- **Token status**: No governance token launched yet (regulatory headwinds + market conditions as of 2026)
- **Whitepaper**: Not publicly available; communicates via X Spaces
- **Weakness**: Generic imagery with blockchain provenance — no domain-specific compliance interpretation. Still needs cities to process the data themselves.

### dClimate
- **Stack**: Polygon + IPFS; Chainlink oracles for validation; DAO governance
- **Data types**: Climate, weather, carbon metrics — **no waterway/maritime data yet**
- **Access**: Stablecoin or fiat subscriptions; free API tier
- **Filecoin**: Partners with Filecoin Green for carbon data only
- **Weakness for us**: Opportunity — AkuaDome would be the FIRST waterway enforcement dataset publisher on dClimate

### Ocean Protocol
- **Model**: Data NFT → ERC20 datatokens → Ocean Market; pay-per-query
- **Privacy**: Compute-to-Data (C2D) — algorithms run on data without raw data leaving publisher
- **Marine/drone data**: **Zero confirmed integrations** — massive first-mover opportunity
- **Relevant for us**: C2D is the correct architecture for sensitive regulatory records (hull numbers, enforcement flags)

---

## AkuaDome's Structural Advantages

### 1. Compliance Verdicts, Not Pixels

Spexi sells imagery. AkuaDome sells **decisions**:
- `dwell_status: RED` → enforcement candidate, $500/day fine
- `at_risk_tier: CRITICAL` → VTIP removal eligible, $5,800 avoided cost
- `trap_legal_status: ILLEGAL` → DERM enforcement action

Government clients pay 10-100x more for a compliance verdict than for a pile of drone photos to process themselves. State Farm (already a Spexi buyer) pays for at-risk vessel data to underwrite marine insurance — that's a direct AkuaDome revenue stream.

### 2. Chain-of-Custody for Legal Proceedings

LayerDrone mints a soulbound NFT per flight. AkuaDome does more:
- SHA-256 of the full MISB ST 0601 KLV telemetry block (per-frame, ~200 bytes @ 30 FPS)
- Pilot FAA Remote Pilot Certificate ID attached to every Observation
- Frozen, append-only Observation records (Pydantic `model_config = {"frozen": True}`)
- ProvenanceRecord with canonical JSON signature

This meets the evidentiary standard for Florida administrative hearings (FS 327.4108 enforcement). LayerDrone's NFT does not.

### 3. Esri Integration — Go Deeper Than Spexi

Spexi: GeoJSON file exports → user imports manually.
AkuaDome target: **Hosted ArcGIS Online Feature Services** with compliance attributes queryable in ArcGIS Pro / AGOL dashboards. Miami-Dade GIS staff query:
```sql
WHERE dwell_stat = 'red' AND at_risk_n >= 3
```
...and get a map of enforcement candidates ready for Marine Patrol dispatch. No data wrangling. Zero GIS analyst time.

**Path**: Apply for **Esri Partner Network** (EPN) as a GIS-Ready Solution. Spexi is already there — we position as "compliance-grade maritime analytics" vs. Spexi's "drone imagery."

### 4. Two-Sided Marketplace Posture

Spexi is supply→demand. AkuaDome operates both sides simultaneously:

```
SUPPLY SIDE                          DEMAND SIDE
─────────────────────────────────────────────────────────
SustainaCities pilot network         City of Miami Marine Patrol
  (DePIN: USDC on Base)              FWC — at-risk scoring
LayerDrone network (partner)         Miami-Dade DERM
Spexi network (data buyer, not       State Farm / marine insurers
  competitor — buy their data,       AI training labs (OpenAI, NVIDIA,
  add compliance layer, resell)        Google — spatial model training)
                                     Autonomous nav (Uber, Amazon)
                                     MiamiVerse / SustainaCities DataHub
```

**Key insight from slide 1**: OpenAI, Google, NVIDIA need training data for Spatial AI and Large Geospatial Models. AkuaDome's statute-aligned, chain-of-custody waterway datasets are exactly the kind of labeled, georeferenced, real-world data they cannot easily generate themselves. **Price accordingly.**

### 5. First-Mover on Environmental Marketplaces

| Marketplace | Status |
|-------------|--------|
| ArcGIS Online | Spexi is there (GeoJSON); we publish Feature Services |
| dClimate | **No waterway data exists** — AkuaDome is first |
| Ocean Protocol | **No drone/maritime data** — AkuaDome is first |
| SustainaCities DataHub | Native integration — AkuaDome is the reference dataset |
| MiamiVerse | 3D Tiles + compliance overlay — AkuaDome exclusive |

---

## Revenue Model

### Tier 1 — Government Subscription (B2G)
| Client | Annual Value | Data |
|--------|-------------|------|
| City of Miami Marine Patrol | $120K–$250K | Full compliance dashboard, RED alerts |
| FWC | $80K–$150K | At-risk vessel early warning + VTIP pathway |
| Miami-Dade DERM | $60K–$100K | Trap compliance + debris change detection |
| Miami-Dade OEM | $40K–$80K | FEMA Section 428 damage assessment layer |

### Tier 2 — Insurance Data Feed (B2B)
State Farm is already a Spexi buyer — for imagery. They want **underwriting intelligence**:
- Per-vessel at-risk score + dwell history = marine insurance risk factor
- **Price**: $2–5/vessel/year at scale; ~50,000 vessels in South Florida = $100K–$250K ARR

### Tier 3 — Decentralized Marketplace (B2B2C)
| Channel | Model | Revenue |
|---------|-------|---------|
| Ocean Protocol | Datatoken per-query | $1–5/query; C2D for sensitive |
| dClimate | Stablecoin subscription | $200–500/mo per subscriber |
| ArcGIS Marketplace | Hosted layer subscription | $50–200/mo per seat |
| SustainaCities DataHub | Revenue share | 70% to AkuaDome |

### Tier 4 — AI Training Data (B2B, premium)
- Labeled, statute-aligned, chain-of-custody aerial maritime dataset
- **Price**: $50K–$500K per data bundle for spatial AI training
- Buyers: OpenAI, Google DeepMind, NVIDIA Omniverse, Esri

---

## DePIN Token Economics (Pilot Incentives)

LayerDrone pays pilots USDC on Base. AkuaDome can do the same — and better:

```
Proposed AkuaDome DePIN Revenue Split (per dataset sale):
  70% → Pilot who flew the flight (USDC on Base)
  20% → SustainaCities protocol treasury (DataHub ops)
  10% → Data quality staking pool (slashable if data rejected)

Reputation system:
  Each pilot accumulates non-transferable FlightCred NFT (soulbound, same as LayerDrone)
  FlightCred score determines:
    - Access to higher-value missions (FEMA, law enforcement)
    - Staking bonus (top pilots earn extra from quality pool)
    - Priority dispatch from SustainaCities mission queue

Differentiation vs LayerDrone:
  - LayerDrone: generic imagery + USDC
  - AkuaDome: compliance-graded data + USDC + FlightCred + mission access tiers
  - Better pilot retention: missions have statutory value → higher pay → better pilots → better data
```

---

## Go-To-Market: Beat Spexi at Their Own Game

### Phase 1 — Capture the Government Channel (Months 1–6)
1. Publish AkuaDome Feature Services to AGOL — **Esri Partner Network** application
2. First dClimate series registration: `aquadome.waterway.dwell.miami`
3. Ocean Protocol: publish dwell + at-risk datatokens (C2D for sensitive records)
4. Close Marine Patrol + FWC as anchor government clients (proof of regulatory alignment)

### Phase 2 — Own the Insurance Channel (Months 6–12)
1. State Farm outreach: position as "compliance intelligence" layer on top of Spexi's imagery
2. Build at-risk vessel API: `GET /v1/vessel/{entity_id}/risk-score` → JSON underwriting signal
3. Partner with Spexi: **buy their raw imagery, add compliance layer, resell** — they become supply, AkuaDome becomes value-add

### Phase 3 — AI Training Data Plays (Months 12–18)
1. Produce labeled GeoParquet dataset bundles: vessel + trap + debris, statute-tagged
2. List on Ocean Protocol as premium C2D compute assets
3. Approach NVIDIA Omniverse, Esri ArcGIS AI (Esri is a Spexi customer — cross-sell)
4. Publish to SustainaCities DataHub as reference dataset for city-scale spatial AI

### Phase 4 — MiamiVerse as Distribution (Months 18–24)
1. AkuaDome compliance overlay is the default waterway layer in MiamiVerse
2. Every Miami resident can see their neighborhood's anchoring compliance status in 3D
3. Field officers use Scaniverse AR (Niantic VPS) to see compliance flags on-site
4. City Council sees the real-time compliance heat map — political alignment for budget

---

## Integration Architecture (Four Channels Simultaneously)

```
AkuaDome Pipeline completion
         │
         ├──► arcgis_online.py
         │    AGOLPublisher.publish_entity_layer()
         │    → Hosted Feature Service with dwell_stat, at_risk, trap_stat fields
         │    → Esri Marketplace listing ($50–200/seat/mo)
         │
         ├──► ocean_protocol.py
         │    OceanDataPublisher.publish_geoparquet()
         │    → Data NFT + ERC20 datatokens on Polygon
         │    → C2D pool for sensitive regulatory records
         │    → $1–5/query on Ocean Market
         │
         ├──► dclimate.py
         │    DClimatePublisher.publish_flight_to_all_series()
         │    → IPFS upload → Polygon on-chain registration
         │    → dClimate marketplace (stablecoin subscription)
         │    → aquadome.waterway.dwell / at_risk / change series
         │
         └──► spatial/stac_catalog.py (already built)
              STACCatalogBuilder.build_item()
              → SustainaCities DataHub STAC Item
              → MiamiVerse 3D Tiles layer
              → Cesium ion asset URL
```

---

## The Knock-Out Punch vs. Spexi

Spexi's slide says the current data infrastructure is "insufficient" for Spatial AI, Metaverse/AR, and autonomous nav. They're right — and they're positioning themselves as the fix.

**AkuaDome's counter-position**: Spexi standardizes data collection. We standardize **regulatory intelligence**. These are complementary, not competing, until Spexi tries to add the compliance layer — which requires statutory expertise (HB 481, FWC, CJIS) and law enforcement data infrastructure that a Canadian drone startup cannot replicate.

**Partnership > competition for now**: Partner with Spexi/LayerDrone as data supply. Buy their imagery (900x more detailed than satellites). Add AkuaDome's compliance layer. Sell the combined product to government and insurance at 10x the price of raw imagery.

**Then beat them**: Once AkuaDome owns the compliance data channel and has government contracts, any competing compliance analytics product must match our statutory depth and chain-of-custody standard — which is a multi-year moat.

> *"Primero aprender a caminar, luego correr."* — Close the government contracts first. The marketplace follows the contracts.
