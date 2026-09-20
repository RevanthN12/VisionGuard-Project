"""
behavior_analysis.py — Vision Guard Abnormal Crowd Behavior Detection Module
Combines density, movement, and turbulence into behavioral classification.
"""

import config
from collections import deque

# ── Status constants ─────────────────────────────────────────────────────────
STATUS_NORMAL     = "NORMAL"
STATUS_SUSPICIOUS = "SUSPICIOUS"
STATUS_ABNORMAL   = "ABNORMAL"
STATUS_DANGEROUS  = "DANGEROUS"

STATUS_COLORS = {
    STATUS_NORMAL:     "#22C55E",
    STATUS_SUSPICIOUS: "#EAB308",
    STATUS_ABNORMAL:   "#F97316",
    STATUS_DANGEROUS:  "#EF4444",
}


class BehaviorAnalyzer:
    """
    Detects abnormal crowd behavior by fusing density and movement signals.

    Behaviors detected:
    - Sudden rushing / panic movement
    - Rapid direction changes
    - Crowd turbulence
    - Prolonged high-density congestion
    - Sudden gathering / dispersal
    - Opposing crowd flows (turbulence proxy)
    """

    def __init__(self):
        self._density_hist  = deque(maxlen=60)
        self._speed_hist    = deque(maxlen=60)
        self._turb_hist     = deque(maxlen=60)
        self._count_hist    = deque(maxlen=60)
        self._congestion_frames = 0

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, density_result: dict, movement_result: dict) -> dict:
        """
        Analyse behavior from density + movement module outputs.

        Returns dict:
          status, status_color, score (0-100),
          flags (list of active behavior flags), description
        """
        d_score    = density_result.get("density_score", 0.0)
        d_level    = density_result.get("level", "LOW")
        m_speed    = movement_result.get("speed", 0.0)
        m_turb     = movement_result.get("turbulence", 0.0)
        m_accel    = movement_result.get("acceleration", 0.0)
        m_level    = movement_result.get("level", "NONE")
        is_panic   = movement_result.get("is_panic", False)
        count      = density_result.get("person_count", 0)

        self._density_hist.append(d_score)
        self._speed_hist.append(m_speed)
        self._turb_hist.append(m_turb)
        self._count_hist.append(count)

        flags = []

        # ── Panic / Sudden rushing ────────────────────────────────────────
        if is_panic or m_speed > config.MOVE_PANIC:
            flags.append("Panic Movement Detected")

        # ── Rapid acceleration ────────────────────────────────────────────
        if abs(m_accel) > 3.0:
            flags.append("Sudden Crowd Acceleration")

        # ── Crowd turbulence (opposing flows) ─────────────────────────────
        if m_turb > 6.0:
            flags.append("Crowd Turbulence / Opposing Flows")

        # ── Prolonged high density (congestion) ───────────────────────────
        if d_level in ("HIGH", "CRITICAL") and count >= 3:
            self._congestion_frames += 1
        else:
            self._congestion_frames = max(0, self._congestion_frames - 2)

        if self._congestion_frames >= config.CONGESTION_FRAMES:
            flags.append(f"Prolonged Congestion ({self._congestion_frames} frames)")

        # ── Sudden gathering detection ────────────────────────────────────
        if len(self._count_hist) >= 10:
            recent_avg  = sum(list(self._count_hist)[-5:]) / 5
            earlier_avg = sum(list(self._count_hist)[:5])  / 5
            if earlier_avg > 0 and (recent_avg - earlier_avg) / earlier_avg > 0.40:
                flags.append("Sudden Crowd Gathering")
            elif earlier_avg > 0 and (earlier_avg - recent_avg) / earlier_avg > 0.40:
                flags.append("Sudden Crowd Dispersal")

        # ── High density + high movement ──────────────────────────────────
        if d_level in ("HIGH", "CRITICAL") and m_level in ("HIGH", "PANIC"):
            flags.append("Dangerous Density + High Speed")

        # ── Score computation ────────────────────────────────────────────
        score = self._compute_score(d_score, m_speed, m_turb, flags)

        # ── Status classification ─────────────────────────────────────────
        if score >= 80:
            status = STATUS_DANGEROUS
        elif score >= 55:
            status = STATUS_ABNORMAL
        elif score >= 30:
            status = STATUS_SUSPICIOUS
        else:
            status = STATUS_NORMAL

        description = self._describe(flags, status)

        return {
            "status":       status,
            "status_color": STATUS_COLORS[status],
            "score":        round(score, 1),
            "flags":        flags,
            "description":  description,
            "congestion_frames": self._congestion_frames,
        }

    def reset(self):
        self._density_hist.clear()
        self._speed_hist.clear()
        self._turb_hist.clear()
        self._count_hist.clear()
        self._congestion_frames = 0

    # ── Internal ──────────────────────────────────────────────────────────────

    def _compute_score(self, d_score, speed, turb, flags) -> float:
        base   = d_score * 0.40
        mv     = min(speed / config.MOVE_PANIC, 1.0) * 30
        tb     = min(turb / 10.0, 1.0) * 15
        flag_b = min(len(flags) * 8, 25)
        return min(base + mv + tb + flag_b, 100.0)

    def _describe(self, flags: list, status: str) -> str:
        if not flags:
            return "Crowd behavior appears normal. No anomalies detected."
        return f"Status: {status}. Detected: " + "; ".join(flags) + "."
