"""
Florida Vessel Hull Number OCR

Extracts Florida registration numbers (format: FL-XXXXXX-XX or similar)
from vessel transom/hull image crops.

Engine: PaddleOCR (Apache-2.0) — recommended default for small/complex text.
Fallback: TrOCR (MIT) for weathered/handwritten text.

Pipeline:
  1. Super-resolve the detection crop (ESRGAN or Real-ESRGAN, check license).
  2. Preprocess: contrast enhancement, deskew.
  3. OCR pass.
  4. Regex validation against FL number pattern.

Avoid Surya OCR: GPL-3.0 code + restrictive "AI Pubs Rail-M" model license
(free only under $2M revenue) — disqualifying for a commercial SaaS.
"""

from __future__ import annotations

import re

import numpy as np

# Florida vessel registration number pattern: FL-XXXXX-XX (letters+digits)
_FL_NUMBER_RE = re.compile(r"\bFL[\s\-]?([A-Z0-9]{4,6})[\s\-]?([A-Z]{2})\b", re.IGNORECASE)


class HullNumberOCR:
    """
    Extracts and validates Florida hull registration numbers from image crops.

    Usage:
        ocr = HullNumberOCR()
        ocr.load()
        text, confidence = ocr.read(crop_bgr)
    """

    def __init__(self, engine: str = "paddleocr", device: str = "cuda") -> None:
        if engine not in {"paddleocr", "doctr", "easyocr", "trocr"}:
            raise ValueError("engine must be one of: paddleocr, doctr, easyocr, trocr")
        self.engine = engine
        self.device = device
        self._ocr = None

    def load(self) -> None:
        if self.engine == "paddleocr":
            try:
                from paddleocr import PaddleOCR  # type: ignore[import]
                self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            except ImportError:
                raise ImportError(
                    "PaddleOCR not installed. Run: pip install paddleocr\n"
                    "License: Apache-2.0"
                )
        elif self.engine == "easyocr":
            try:
                import easyocr  # type: ignore[import]
                self._ocr = easyocr.Reader(["en"], gpu=(self.device == "cuda"))
            except ImportError:
                raise ImportError("EasyOCR not installed. Run: pip install easyocr  (Apache-2.0)")

    def read(self, crop_bgr: np.ndarray) -> tuple[str | None, float]:
        """
        Returns (normalized_fl_number, confidence).
        Returns (None, 0.0) if no valid FL number found.
        """
        assert self._ocr is not None, "Call load() first"
        raw_text, confidence = self._run_ocr(crop_bgr)
        normalized = self._parse_fl_number(raw_text)
        return normalized, confidence if normalized else 0.0

    def _run_ocr(self, crop_bgr: np.ndarray) -> tuple[str, float]:
        if self.engine == "paddleocr":
            result = self._ocr.ocr(crop_bgr, cls=True)
            if not result or not result[0]:
                return "", 0.0
            texts = [(line[1][0], line[1][1]) for line in result[0]]
            combined = " ".join(t for t, _ in texts)
            avg_conf = sum(c for _, c in texts) / len(texts)
            return combined, avg_conf

        if self.engine == "easyocr":
            result = self._ocr.readtext(crop_bgr)
            if not result:
                return "", 0.0
            texts = [(r[1], r[2]) for r in result]
            combined = " ".join(t for t, _ in texts)
            avg_conf = sum(c for _, c in texts) / len(texts)
            return combined, avg_conf

        return "", 0.0

    @staticmethod
    def _parse_fl_number(raw: str) -> str | None:
        m = _FL_NUMBER_RE.search(raw.upper())
        if m:
            return f"FL-{m.group(1)}-{m.group(2)}"
        return None
