"""
DERM Change Detection Engine

Compares orthomosaics across flight passes to detect:
  - New debris / illegal dumping
  - Derelict vessel settling / sinking progression
  - Trap buoys appearing outside permitted areas

Uses Open-CD (Apache-2.0) built on OpenMMLab — verify individual model weights
before production deployment. Bitemporal satellite/drone imagery pairs.

Note on ODM/WebODM: AGPL-3.0 — do NOT fork or serve over the network.
Build orthorectification from GDAL/rasterio/PDAL or license a commercial engine.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np


@dataclass
class ChangeEvent:
    """One detected change between two flight passes."""
    flight_before_id: uuid.UUID
    flight_after_id: uuid.UUID
    detected_at: datetime
    lon: float
    lat: float
    change_type: str          # "new_debris" | "debris_removed" | "vessel_settled" | "trap_appeared"

    change_id: uuid.UUID = field(default_factory=uuid.uuid4)
    area_m2: float | None = None
    confidence: float = 0.0
    change_mask: np.ndarray | None = None  # binary mask in orthomosaic pixel space
    thumbnail_path: str | None = None       # path to cropped visual evidence
    tenant_id: str = ""
    requires_field_verification: bool = True


class ChangeDetectionEngine:
    """
    Bitemporal change detection between drone orthomosaic passes.

    Backend: Open-CD (Apache-2.0), BIT / ChangeFormer models.
    Install: pip install opencd  (verify individual model weight licenses)

    Usage:
        engine = ChangeDetectionEngine()
        engine.load(model_name="bit_r18")
        events = engine.detect(ortho_before, ortho_after, flight_before_id, flight_after_id)
    """

    SUPPORTED_MODELS = {
        "bit_r18": "BIT (Binary change detection Transformer)",
        "changeformer_mit-b0": "ChangeFormer MiT-B0",
    }

    def __init__(self, model_name: str = "bit_r18", confidence_threshold: float = 0.5) -> None:
        self.model_name = model_name
        self.confidence_threshold = confidence_threshold
        self._model = None

    def load(self) -> None:
        try:
            import mmcd  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "Open-CD not installed. See: https://github.com/likyoo/open-cd\n"
                "License: Apache-2.0 (verify individual model weight licenses)"
            )
        # Wire: mmcd.apis.init_detector(config, checkpoint, device)
        self._model = None  # placeholder

    def detect(
        self,
        ortho_before: np.ndarray,
        ortho_after: np.ndarray,
        flight_before_id: uuid.UUID,
        flight_after_id: uuid.UUID,
        tenant_id: str = "",
    ) -> list[ChangeEvent]:
        """
        Returns list of ChangeEvent for pixels exceeding confidence threshold.
        Recall-weighted: low threshold to minimize missed illegal dumping.
        """
        if self._model is None:
            raise RuntimeError("Call load() before detect()")

        # Placeholder — real impl calls mmcd inference + connected-component labeling
        events: list[ChangeEvent] = []
        return events
