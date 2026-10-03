"""Base types for the detection layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np


@dataclass
class DetectionResult:
    """One detection from a single frame."""
    xyxy: np.ndarray           # shape (N, 4) — [x1, y1, x2, y2]
    confidence: np.ndarray     # shape (N,)
    class_id: np.ndarray       # shape (N,)  int indices
    class_names: list[str]     # mapping from class_id int → name
    frame_pts_us: int          # frame timestamp for telemetry alignment
    altitude_m: float | None = None

    @property
    def count(self) -> int:
        return len(self.confidence)


class Detector(Protocol):
    """Every detector adapter must implement this interface."""

    def predict(self, image: np.ndarray, altitude_m: float | None = None) -> DetectionResult: ...

    def load(self, weights_path: str | None = None) -> None: ...
