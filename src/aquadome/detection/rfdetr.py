"""
RF-DETR detector wrapper (Apache-2.0, Roboflow, ICLR 2026).

RF-DETR-2XL achieves 60.1 AP on COCO and 60.5 mAP at 25 FPS on an NVIDIA T4.
This is the PRIMARY detector for AquaDome.

Install:
    pip install rfdetr   # Apache-2.0

The wrapper supports altitude-aware tiling: at high altitudes (> 100 m AGL)
vessels subtend fewer pixels, so we tile the frame into overlapping patches
and run inference on each patch before NMS-merging results.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .base import DetectionResult
from .tiling import TiledInference

# AquaDome maritime class mapping
_MARITIME_CLASSES = [
    "vessel",
    "trap_buoy",
    "debris",
    "structure",
    "unknown",
]


class RFDETRDetector:
    """
    Wrapper around the RF-DETR model for maritime object detection.

    Usage:
        detector = RFDETRDetector(device="cuda")
        detector.load()
        result = detector.predict(frame_bgr, altitude_m=80.0)
    """

    def __init__(
        self,
        model_variant: str = "rfdetr-base",  # rfdetr-nano | rfdetr-base | rfdetr-large | rfdetr-2xl
        device: str = "cuda",
        confidence_threshold: float = 0.4,
        altitude_tiling: bool = True,
    ) -> None:
        self.model_variant = model_variant
        self.device = device
        self.confidence_threshold = confidence_threshold
        self.altitude_tiling = altitude_tiling
        self._model = None
        self._tiler: TiledInference | None = None

    def load(self, weights_path: str | None = None) -> None:
        try:
            from rfdetr import RFDETRBase, RFDETRLarge  # type: ignore[import]

            cls = RFDETRBase if "base" in self.model_variant else RFDETRLarge
            self._model = cls(pretrain_weights=weights_path, device=self.device)
        except ImportError:
            raise ImportError(
                "RF-DETR not installed. Run: pip install rfdetr\n"
                "License: Apache-2.0 — https://github.com/roboflow/rf-detr"
            )
        if self.altitude_tiling:
            self._tiler = TiledInference(base_predictor=self._run_single)

    def _run_single(self, image: np.ndarray) -> DetectionResult:
        assert self._model is not None, "Call load() first"
        import supervision as sv  # type: ignore[import]

        detections: sv.Detections = self._model.predict(image, threshold=self.confidence_threshold)
        return DetectionResult(
            xyxy=detections.xyxy,
            confidence=detections.confidence,
            class_id=detections.class_id,
            class_names=_MARITIME_CLASSES,
            frame_pts_us=0,
        )

    def predict(self, image: np.ndarray, altitude_m: float | None = None) -> DetectionResult:
        if self.altitude_tiling and self._tiler and altitude_m and altitude_m > 60.0:
            return self._tiler.predict(image, altitude_m=altitude_m)
        return self._run_single(image)
