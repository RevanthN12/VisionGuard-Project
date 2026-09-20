"""
violence_detection.py — Vision Guard Violence Detection Module
Motion-heuristic implementation only.
Results are labeled "Possible Aggressive Motion" — NOT confirmed violence.
A proper implementation requires a trained CNN/LSTM video classifier.
"""

import numpy as np
from collections import deque
import config


class ViolenceDetector:
    """
    Heuristic violence detector based on motion intensity patterns.

    IMPORTANT: This module uses motion-based heuristics only.
    Do NOT present results as confirmed violence detection.
    Label: "Possible Aggressive Motion"
    """

    def __init__(self):
        self._speed_hist = deque(maxlen=30)
        self._turb_hist  = deque(maxlen=30)

    def analyze(self, movement_result: dict,
                inject_simulation: bool = False) -> dict:
        """
        Estimate possible aggressive motion from movement signals.

        Returns dict:
          detected (bool), label, score (0-100), confidence_note
        """
        speed = movement_result.get("speed",      0.0)
        turb  = movement_result.get("turbulence", 0.0)
        accel = abs(movement_result.get("acceleration", 0.0))

        self._speed_hist.append(speed)
        self._turb_hist.append(turb)

        avg_speed = sum(self._speed_hist) / max(len(self._speed_hist), 1)
        avg_turb  = sum(self._turb_hist)  / max(len(self._turb_hist),  1)

        # Heuristic score: extreme speed + high turbulence + sharp acceleration
        score  = min(avg_speed / config.MOVE_PANIC * 50, 50)
        score += min(avg_turb  / 10.0 * 30, 30)
        score += min(accel     / 5.0  * 20, 20)
        score  = round(min(score, 100.0), 1)

        if inject_simulation:
            score = max(score, 82.0)

        detected = score >= 65.0

        return {
            "detected":         detected,
            "label":            "Possible Aggressive Motion" if detected else "None",
            "score":            score,
            "confidence_note":  "Heuristic (motion-based) — not a trained classifier.",
        }
