"""Vessel re-identification — FastReID (Apache-2.0) + DINOv2 (Apache-2.0 checkpoint)."""

from .embeddings import VesselEmbedder
from .resolver import CrossFlightResolver

__all__ = ["VesselEmbedder", "CrossFlightResolver"]
