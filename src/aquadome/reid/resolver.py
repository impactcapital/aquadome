"""
Cross-flight entity resolution — the core proprietary moat.

Resolves observations from multiple flights into persistent Entity records
using three evidence channels:
  1. Appearance embedding similarity (FastReID / DINOv2)
  2. Geospatial proximity (anchor radius, bearing from last known position)
  3. Hull OCR match (FL registration number if legible)

This enables dwell-time computation and vessel identity persistence WITHOUT
AIS, which is critical for liveaboards and unregistered vessels.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from ..ontology.enums import ResolutionMethod
from ..ontology.models import Entity, EntityType, Observation, Point2D


@dataclass
class ResolutionCandidate:
    entity_id: uuid.UUID
    embedding: np.ndarray
    last_position: Point2D
    last_seen: datetime
    ocr_text: str | None = None
    score: float = 0.0


class CrossFlightResolver:
    """
    Matches a new Observation to an existing Entity, or creates a new one.

    Resolution priority:
      1. OCR match (FL number) — deterministic if confidence > threshold
      2. Embedding + geo combined score
    """

    def __init__(
        self,
        similarity_threshold: float = 0.75,
        ocr_confidence_threshold: float = 0.85,
        max_gap_hours: float = 72.0,
        max_distance_m: float = 500.0,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.ocr_confidence_threshold = ocr_confidence_threshold
        self.max_gap_hours = max_gap_hours
        self.max_distance_m = max_distance_m

    def _haversine_m(self, a: Point2D, b: Point2D) -> float:
        import math
        R = 6_371_000.0
        lat1, lon1 = math.radians(a.lat), math.radians(a.lon)
        lat2, lon2 = math.radians(b.lat), math.radians(b.lon)
        dlat, dlon = lat2 - lat1, lon2 - lon1
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return 2 * R * math.asin(math.sqrt(h))

    def _geo_score(self, obs_pos: Point2D, candidate: ResolutionCandidate) -> float:
        dist = self._haversine_m(obs_pos, candidate.last_position)
        if dist > self.max_distance_m:
            return 0.0
        return 1.0 - (dist / self.max_distance_m)

    def _emb_score(self, obs_emb: np.ndarray, candidate: ResolutionCandidate) -> float:
        if obs_emb is None or candidate.embedding is None:
            return 0.0
        return float(np.dot(obs_emb / (np.linalg.norm(obs_emb) + 1e-9),
                             candidate.embedding / (np.linalg.norm(candidate.embedding) + 1e-9)))

    def resolve(
        self,
        observation: Observation,
        candidates: list[ResolutionCandidate],
    ) -> tuple[uuid.UUID | None, ResolutionMethod | None, float]:
        """
        Returns (matched_entity_id, resolution_method, confidence).
        Returns (None, None, 0.0) if no match — caller should create a new Entity.
        """
        # OCR priority path
        if (
            observation.ocr_text
            and observation.ocr_confidence
            and observation.ocr_confidence >= self.ocr_confidence_threshold
        ):
            for c in candidates:
                if c.ocr_text == observation.ocr_text:
                    return c.entity_id, ResolutionMethod.OCR_ONLY, 1.0

        # Embedding + geo combined
        best_score = 0.0
        best_candidate: ResolutionCandidate | None = None

        for c in candidates:
            geo = self._geo_score(observation.geometry, c)
            if geo == 0.0:
                continue
            emb_s = (
                self._emb_score(np.array(observation.reid_embedding), c)
                if observation.reid_embedding
                else 0.5
            )
            combined = 0.6 * emb_s + 0.4 * geo
            if combined > best_score:
                best_score = combined
                best_candidate = c

        if best_candidate and best_score >= self.similarity_threshold:
            method = (
                ResolutionMethod.EMBEDDING_GEO_OCR
                if observation.ocr_text
                else ResolutionMethod.EMBEDDING_GEO
            )
            return best_candidate.entity_id, method, best_score

        return None, None, 0.0
