"""
Multi-object tracker wrapping roboflow/trackers (Apache-2.0).

Algorithm selection:
  BoT-SORT  — default; camera-motion compensation + appearance embeddings,
               best for a moving drone platform with wind drift.
  OC-SORT   — handles non-linear vessel drift (tidal/current).
  ByteTrack — use when detector is very strong and appearance is stable.

Optimize HOTA (not MOTA) for maritime vessel re-ID continuity.
"""

from __future__ import annotations

import numpy as np

from ..detection.base import DetectionResult


class AquaDomeTracker:
    """
    Wraps boxmot (roboflow/trackers) to produce track IDs per frame.

    boxmot (Apache-2.0): https://github.com/mikel-brostrom/boxmot
    """

    SUPPORTED = {"botsort", "ocsort", "bytetrack", "strongsort"}

    def __init__(
        self,
        algorithm: str = "botsort",
        device: str = "cuda",
        reid_weights: str | None = None,
    ) -> None:
        if algorithm not in self.SUPPORTED:
            raise ValueError(f"algorithm must be one of {self.SUPPORTED}")
        self.algorithm = algorithm
        self.device = device
        self.reid_weights = reid_weights
        self._tracker = None

    def load(self) -> None:
        try:
            from boxmot import BotSort, OcSort, ByteTrack, StrongSort  # type: ignore[import]
        except ImportError:
            raise ImportError(
                "boxmot not installed. Run: pip install boxmot\n"
                "License: Apache-2.0 — https://github.com/mikel-brostrom/boxmot"
            )
        cls_map = {
            "botsort": BotSort,
            "ocsort": OcSort,
            "bytetrack": ByteTrack,
            "strongsort": StrongSort,
        }
        kwargs: dict = {}
        if self.reid_weights:
            kwargs["reid_weights"] = self.reid_weights
        self._tracker = cls_map[self.algorithm](**kwargs)

    def update(self, detections: DetectionResult, frame: np.ndarray) -> np.ndarray:
        """
        Returns an (N, 7) array: [x1, y1, x2, y2, track_id, confidence, class_id].
        """
        assert self._tracker is not None, "Call load() first"
        # boxmot expects (N, 6): [x1, y1, x2, y2, conf, class_id]
        if detections.count == 0:
            return np.zeros((0, 7))
        dets = np.column_stack([
            detections.xyxy,
            detections.confidence[:, None],
            detections.class_id[:, None],
        ])
        tracks = self._tracker.update(dets, frame)
        return tracks
