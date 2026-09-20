"""
density.py — Vision Guard Crowd Density Analysis Module
Estimates density from person count, frame area, and bounding-box occupancy.
"""

import numpy as np
import config


# ── Level constants ──────────────────────────────────────────────────────────
LEVEL_LOW      = "LOW"
LEVEL_MEDIUM   = "MEDIUM"
LEVEL_HIGH     = "HIGH"
LEVEL_CRITICAL = "CRITICAL"

LEVEL_COLORS = {
    LEVEL_LOW:      "#22C55E",
    LEVEL_MEDIUM:   "#EAB308",
    LEVEL_HIGH:     "#F97316",
    LEVEL_CRITICAL: "#EF4444",
}


class DensityAnalyzer:
    """Computes crowd density metrics per frame."""

    def __init__(self,
                 frame_w: int = config.FRAME_WIDTH,
                 frame_h: int = config.FRAME_HEIGHT):
        self.frame_area = frame_w * frame_h
        self._low_thresh  = config.DENSITY_LOW
        self._med_thresh  = config.DENSITY_MEDIUM
        self._high_thresh = config.DENSITY_HIGH

    def analyze(self, detections: list, frame_w: int = None, frame_h: int = None) -> dict:
        """
        Compute density from detection list.

        Args:
            detections : list of detection dicts (must have 'area' and 'box' keys)
            frame_w/h  : optional override frame dimensions

        Returns:
            dict: density_pct, level, level_color, occupied_area, box_coverage_pct,
                  score (0-100), congestion_indicator
        """
        if frame_w and frame_h:
            frame_area = frame_w * frame_h
        else:
            frame_area = self.frame_area

        person_count = len(detections)

        # Occupied pixel area (sum of bounding-box areas)
        occupied = sum(d.get("area", 0) for d in detections)
        occupied = min(occupied, frame_area)

        # Box coverage ratio
        box_coverage = occupied / max(frame_area, 1)

        # Continuous crowd scaling: 1 individual does not constitute a crowd even if close to lens.
        # S_N smoothly transitions from single-person (0.10) to moderate group (0.5) to large crowd (1.0).
        if person_count == 0:
            crowd_scale = 0.0
        elif person_count == 1:
            crowd_scale = 0.12
        else:
            # Smooth saturation curve without abrupt step jumps
            crowd_scale = float(1.0 - np.exp(-person_count / 10.0))

        # Blend visual bounding-box occupancy with crowd scale factor
        effective_occupancy = box_coverage * crowd_scale
        count_intensity = min(person_count / 25.0, 1.0)
        
        density_pct = min(effective_occupancy * 0.55 + count_intensity * 0.45, 1.0)
        score = round(density_pct * 100, 1)
        level = self._classify(density_pct)

        return {
            "density_pct":      round(density_pct, 4),
            "density_score":    score,
            "level":            level,
            "level_color":      LEVEL_COLORS[level],
            "occupied_area":    occupied,
            "box_coverage_pct": round(box_coverage * 100, 1),
            "crowd_scale":      round(crowd_scale, 3),
            "person_count":     person_count,
        }

    def _classify(self, density_pct: float) -> str:
        if density_pct < self._low_thresh:
            return LEVEL_LOW
        elif density_pct < self._med_thresh:
            return LEVEL_MEDIUM
        elif density_pct < self._high_thresh:
            return LEVEL_HIGH
        else:
            return LEVEL_CRITICAL

    def set_thresholds(self, low: float, medium: float, high: float):
        """Allow runtime threshold adjustment."""
        self._low_thresh  = low
        self._med_thresh  = medium
        self._high_thresh = high
