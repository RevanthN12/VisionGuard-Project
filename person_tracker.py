import builtins
_orig_delattr = builtins.delattr
def _safe_delattr(obj, name):
    try:
        _orig_delattr(obj, name)
    except AttributeError:
        pass
builtins.delattr = _safe_delattr

import os
import cv2
import numpy as np
from collections import deque
from ultralytics import YOLO

# 8-way compass labels and their arrow Unicode glyphs
_COMPASS = [
    (337.5, 360,   "E",  "→"),
    (0,     22.5,  "E",  "→"),
    (22.5,  67.5,  "SE", "↘"),
    (67.5,  112.5, "S",  "↓"),
    (112.5, 157.5, "SW", "↙"),
    (157.5, 202.5, "W",  "←"),
    (202.5, 247.5, "NW", "↖"),
    (247.5, 292.5, "N",  "↑"),
    (292.5, 337.5, "NE", "↗"),
]


def _angle_to_compass(dx, dy):
    """Convert (dx, dy) to 8-way compass label and glyph."""
    angle = (np.degrees(np.arctan2(-dy, dx)) + 360) % 360  # 0=right, CCW
    # Convert to clockwise-from-north
    bearing = (90 - angle + 360) % 360
    for lo, hi, label, glyph in _COMPASS:
        if lo <= bearing < hi:
            return label, glyph
    return "E", "→"


class PersonTracker:
    def __init__(self, model_path="models/yolov8n.pt"):
        self.model = YOLO(model_path)
        self.history = {}        # track_id -> deque of (cx, cy)
        self.smoothed_vel = {}   # track_id -> smoothed (vx, vy)

    def get_centroid(self, box):
        x1, y1, x2, y2 = box
        return (int((x1 + x2) / 2), int((y1 + y2) / 2))

    def track(self, frame):
        """
        Runs YOLO+ByteTrack on a frame.
        Returns list of dicts:
          id, box, centroid, speed, direction, compass, arrow_glyph,
          vx, vy,   ← raw smoothed velocity components
          status, trail  ← last N centroid positions for trail drawing
        """
        results = self.model.track(
            frame, persist=True, tracker="bytetrack.yaml", verbose=False
        )
        tracked_persons = []

        if not results or results[0].boxes is None:
            return tracked_persons

        boxes = results[0].boxes
        active_ids = []

        for box in boxes:
            cls_id = int(box.cls[0])
            if cls_id != 0:           # person class only
                continue

            xyxy     = box.xyxy[0].cpu().numpy()
            track_id = int(box.id[0].cpu().numpy()) if box.id is not None else None
            if track_id is None:
                continue

            active_ids.append(track_id)
            centroid = self.get_centroid(xyxy)

            # ── History ──────────────────────────────────────────────────
            if track_id not in self.history:
                self.history[track_id]     = deque(maxlen=20)
                self.smoothed_vel[track_id] = (0.0, 0.0)
            self.history[track_id].append(centroid)

            points = list(self.history[track_id])

            # ── Instantaneous velocity (frame-to-frame) ───────────────────
            vx_raw, vy_raw, speed = 0.0, 0.0, 0.0
            if len(points) >= 2:
                vx_raw = float(points[-1][0] - points[-2][0])
                vy_raw = float(points[-1][1] - points[-2][1])
                speed  = float(np.hypot(vx_raw, vy_raw))

            # ── Exponential smoothing for stable arrows ───────────────────
            alpha = 0.35
            svx, svy = self.smoothed_vel[track_id]
            svx = alpha * vx_raw + (1 - alpha) * svx
            svy = alpha * vy_raw + (1 - alpha) * svy
            self.smoothed_vel[track_id] = (svx, svy)

            # ── Compass direction (from smoothed vector) ───────────────────
            if abs(svx) < 0.8 and abs(svy) < 0.8:
                compass, glyph = "—", "•"       # stationary
            else:
                compass, glyph = _angle_to_compass(svx, svy)

            # ── 5-point direction (legacy) ────────────────────────────────
            if len(points) >= 5:
                dx5 = points[-1][0] - points[0][0]
                dy5 = points[-1][1] - points[0][1]
                if abs(dx5) > abs(dy5):
                    direction = "L→R" if dx5 > 0 else "R→L"
                else:
                    direction = "T→B" if dy5 > 0 else "B→T"
            else:
                direction = "Stable"

            # ── Status ────────────────────────────────────────────────────
            if speed > 18.0:
                status = "Running"
            elif speed > 5.0:
                status = "Moving"
            else:
                status = "Normal"

            tracked_persons.append({
                "id":          track_id,
                "box":         xyxy,
                "centroid":    centroid,
                "speed":       round(speed, 1),
                "direction":   direction,
                "compass":     compass,
                "arrow_glyph": glyph,
                "vx":          svx,
                "vy":          svy,
                "status":      status,
                "trail":       list(points),   # for drawing motion trail
            })

        # Clean up stale histories
        for tid in [t for t in self.history if t not in active_ids]:
            del self.history[tid]
            self.smoothed_vel.pop(tid, None)

        return tracked_persons
