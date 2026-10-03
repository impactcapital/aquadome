"""
Altitude-aware tiled inference for small-object detection.

At high AGL (> 60 m) vessels subtend ~20–40 px on a 4K sensor, falling below
the practical detection floor for most transformers. We tile the frame into
overlapping patches, run the base detector on each, then merge via NMS.

Tile size and overlap are derived from altitude and sensor FOV metadata.
"""

from __future__ import annotations

from typing import Callable

import numpy as np

from .base import DetectionResult


def _nms(
    xyxy: np.ndarray, scores: np.ndarray, iou_threshold: float = 0.5
) -> np.ndarray:
    """Simple greedy NMS. Returns kept indices."""
    if len(scores) == 0:
        return np.array([], dtype=int)
    x1, y1, x2, y2 = xyxy[:, 0], xyxy[:, 1], xyxy[:, 2], xyxy[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
        order = order[1:][iou <= iou_threshold]
    return np.array(keep, dtype=int)


class TiledInference:
    """
    Tiles a full frame into overlapping patches, runs the base predictor on
    each, offsets coordinates back to full-frame space, then merges via NMS.
    """

    def __init__(
        self,
        base_predictor: Callable[[np.ndarray], DetectionResult],
        tile_size: int = 640,
        overlap: float = 0.2,
        iou_threshold: float = 0.5,
    ) -> None:
        self._predict = base_predictor
        self.tile_size = tile_size
        self.overlap = overlap
        self.iou_threshold = iou_threshold

    def _tiles(self, h: int, w: int) -> list[tuple[int, int, int, int]]:
        stride = int(self.tile_size * (1 - self.overlap))
        tiles = []
        y = 0
        while y < h:
            x = 0
            while x < w:
                x2 = min(x + self.tile_size, w)
                y2 = min(y + self.tile_size, h)
                tiles.append((x, y, x2, y2))
                x += stride
            y += stride
        return tiles

    def predict(self, image: np.ndarray, altitude_m: float | None = None) -> DetectionResult:
        h, w = image.shape[:2]
        all_xyxy, all_conf, all_cls = [], [], []
        pts_us = 0
        class_names: list[str] = []

        for x1, y1, x2, y2 in self._tiles(h, w):
            patch = image[y1:y2, x1:x2]
            result = self._predict(patch)
            pts_us = result.frame_pts_us
            class_names = result.class_names
            if result.count == 0:
                continue
            # Offset back to full-frame coordinates
            offset_xyxy = result.xyxy + np.array([x1, y1, x1, y1])
            all_xyxy.append(offset_xyxy)
            all_conf.append(result.confidence)
            all_cls.append(result.class_id)

        if not all_xyxy:
            return DetectionResult(
                xyxy=np.zeros((0, 4)),
                confidence=np.zeros(0),
                class_id=np.zeros(0, dtype=int),
                class_names=class_names,
                frame_pts_us=pts_us,
                altitude_m=altitude_m,
            )

        xyxy = np.concatenate(all_xyxy, axis=0)
        conf = np.concatenate(all_conf, axis=0)
        cls = np.concatenate(all_cls, axis=0)
        keep = _nms(xyxy, conf, self.iou_threshold)

        return DetectionResult(
            xyxy=xyxy[keep],
            confidence=conf[keep],
            class_id=cls[keep],
            class_names=class_names,
            frame_pts_us=pts_us,
            altitude_m=altitude_m,
        )
