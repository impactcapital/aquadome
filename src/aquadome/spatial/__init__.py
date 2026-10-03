"""
AkuaDome Spatial Pipeline — drone imagery → 3D Gaussian Splat → tagged data marketplace.

Modules:
  spexi          — Spexi Geospatial Upload API client (OGC API-Features)
  cesium_ion     — Cesium ion REST API uploader (3D Tiles 2.0)
  stac_catalog   — STAC 1.0 Item builder for SustainaCities DataHub
  tiles3d_tagger — Attaches AkuaDome compliance metadata to 3D Tileset features
"""
