"""
movement.py — Vision Guard Crowd Movement Analysis Module
Uses Farneback Optical Flow with safe grayscale frame handling.
Prevents OpenCV errors: prev0.size() == next0.size()
"""

import cv2
import numpy as np
import config

# ── Movement level constants ─────────────────────────────────────────────────
LEVEL_NONE     = "NONE"
LEVEL_LOW      = "LOW"
LEVEL_MEDIUM   = "MEDIUM"
LEVEL_HIGH     = "HIGH"
LEVEL_PANIC    = "PANIC"

LEVEL_COLORS = {
    LEVEL_NONE:   "#64748B",
    LEVEL_LOW:    "#22C55E",
    LEVEL_MEDIUM: "#EAB308",
    LEVEL_HIGH:   "#F97316",
    LEVEL_PANIC:  "#EF4444",
}

# 8-way compass from angle
_COMPASS_LABELS = ["E","NE","N","NW","W","SW","S","SE"]


class MovementAnalyzer:
    """
    Computes optical-flow based crowd movement metrics.

    Design contract:
    - Frames are ALWAYS converted to grayscale before flow computation.
    - Dimensions are validated / resized before cv2.calcOpticalFlowFarneback.
    - The previous frame is always initialized from the first valid frame.
    """

    def __init__(self,
                 target_w: int = config.FRAME_WIDTH,
                 target_h: int = config.FRAME_HEIGHT):
        self._target_w   = target_w
        self._target_h   = target_h
        self._prev_gray  = None          # previous grayscale frame
        self._speed_hist = []            # rolling speed history
        self._hist_size  = 30

        # Farneback parameters (tuned for CPU)
        self._fb_params = dict(
            pyr_scale   = 0.5,
            levels      = 3,
            winsize     = 13,
            iterations  = 3,
            poly_n      = 5,
            poly_sigma  = 1.2,
            flags       = 0,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze(self, frame) -> dict:
        """
        Analyze movement in the current frame vs the previous frame.

        Args:
            frame : BGR or grayscale ndarray

        Returns:
            dict with: speed, direction, turbulence, acceleration,
                       level, level_color, flow_vis, is_panic
        """
        gray = self._to_gray_resized(frame)

        # ── First frame — initialise without computing flow ───────────────
        if self._prev_gray is None:
            self._prev_gray = gray
            return self._zero_result()

        # ── Safety check — ensure identical size ──────────────────────────
        if gray.shape != self._prev_gray.shape:
            self._prev_gray = gray
            return self._zero_result()

        # ── Compute Farneback optical flow ────────────────────────────────
        try:
            flow = cv2.calcOpticalFlowFarneback(
                self._prev_gray, gray, None, **self._fb_params
            )
        except cv2.error as e:
            print(f"[Movement] Optical flow error: {e}")
            self._prev_gray = gray
            return self._zero_result()

        self._prev_gray = gray

        # ── Decompose flow field ──────────────────────────────────────────
        fx, fy = flow[..., 0], flow[..., 1]
        magnitude, angle_rad = cv2.cartToPolar(fx, fy, angleInDegrees=False)

        mean_speed      = float(np.mean(magnitude))
        max_speed       = float(np.max(magnitude))
        mean_angle_deg  = float(np.degrees(np.mean(angle_rad)) % 360)

        # Turbulence = std-dev of local magnitudes
        turbulence = float(np.std(magnitude))

        # Acceleration = change in mean speed vs history
        self._speed_hist.append(mean_speed)
        if len(self._speed_hist) > self._hist_size:
            self._speed_hist.pop(0)
        accel = 0.0
        if len(self._speed_hist) >= 2:
            accel = self._speed_hist[-1] - self._speed_hist[-2]

        # ── Classify ─────────────────────────────────────────────────────
        level    = self._classify_speed(mean_speed)
        is_panic = (level == LEVEL_PANIC or
                    (turbulence > 5.0 and mean_speed > config.MOVE_HIGH))

        # ── Flow visualisation (optional — for display) ────────────────────
        flow_vis = self._draw_flow(frame, flow, magnitude)

        return {
            "speed":        round(mean_speed, 2),
            "max_speed":    round(max_speed, 2),
            "direction":    self._angle_to_compass(mean_angle_deg),
            "angle_deg":    round(mean_angle_deg, 1),
            "turbulence":   round(turbulence, 2),
            "acceleration": round(accel, 2),
            "level":        level,
            "level_color":  LEVEL_COLORS[level],
            "flow_vis":     flow_vis,
            "is_panic":     is_panic,
            "score":        self._speed_to_score(mean_speed, turbulence, accel),
        }

    def reset(self):
        """Clear previous frame buffer."""
        self._prev_gray  = None
        self._speed_hist = []

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _to_gray_resized(self, frame) -> np.ndarray:
        """Convert any frame to a correctly sized grayscale image."""
        if frame is None:
            return np.zeros((self._target_h, self._target_w), dtype=np.uint8)
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame.copy()
        if gray.shape[0] != self._target_h or gray.shape[1] != self._target_w:
            gray = cv2.resize(gray, (self._target_w, self._target_h),
                              interpolation=cv2.INTER_LINEAR)
        return gray

    def _classify_speed(self, speed: float) -> str:
        if speed < config.MOVE_LOW:
            return LEVEL_LOW
        elif speed < config.MOVE_MEDIUM:
            return LEVEL_MEDIUM
        elif speed < config.MOVE_HIGH:
            return LEVEL_HIGH
        else:
            return LEVEL_PANIC

    def _speed_to_score(self, speed: float, turbulence: float, accel: float = 0.0) -> float:
        """Return 0-100 movement danger score based on speed, turbulence, and sudden acceleration."""
        s = min(speed / config.MOVE_PANIC, 1.0) * 55.0
        t = min(turbulence / 8.0, 1.0) * 30.0
        a = min(abs(accel) / 3.0, 1.0) * 15.0
        return round(min(s + t + a, 100.0), 1)

    def _angle_to_compass(self, deg: float) -> str:
        idx = int((deg + 22.5) / 45) % 8
        return _COMPASS_LABELS[idx]

    def _draw_flow(self, frame, flow, magnitude) -> np.ndarray:
        """Draw sparse optical flow arrows on a dark overlay."""
        vis = frame.copy()
        step = 24
        h, w = vis.shape[:2]
        for y in range(0, h, step):
            for x in range(0, w, step):
                mag = magnitude[y, x]
                if mag < 0.5:
                    continue
                fx_val = flow[y, x, 0]
                fy_val = flow[y, x, 1]
                ex = int(x + fx_val * 3)
                ey = int(y + fy_val * 3)
                ex = max(0, min(ex, w - 1))
                ey = max(0, min(ey, h - 1))
                intensity = min(int(mag * 20), 255)
                color = (0, intensity, 255 - intensity)
                cv2.arrowedLine(vis, (x, y), (ex, ey), color, 1, tipLength=0.4)
        return vis

    def _zero_result(self) -> dict:
        return {
            "speed": 0.0, "max_speed": 0.0,
            "direction": "—", "angle_deg": 0.0,
            "turbulence": 0.0, "acceleration": 0.0,
            "level": LEVEL_NONE, "level_color": LEVEL_COLORS[LEVEL_NONE],
            "flow_vis": None, "is_panic": False, "score": 0.0,
        }
