"""
head_detector.py — VisionGuard Dedicated Head Detection Module
Detects head / upper-body regions when lower body or full body is not visible,
occluded, or in dense crowds.
"""

import cv2
import numpy as np
import os
import config

class HeadDetector:
    def __init__(self):
        self.upperbody_cascade = None
        self.profile_cascade = None
        self.load_cascades()

    def load_cascades(self):
        try:
            ub_path = cv2.data.haarcascades + 'haarcascade_upperbody.xml'
            pf_path = cv2.data.haarcascades + 'haarcascade_profileface.xml'
            if os.path.exists(ub_path):
                self.upperbody_cascade = cv2.CascadeClassifier(ub_path)
            if os.path.exists(pf_path):
                self.profile_cascade = cv2.CascadeClassifier(pf_path)
        except Exception as e:
            print(f"[HeadDetector] Error loading cascades: {e}")

    def detect(self, frame, conf_threshold: float = None):
        """
        Detect head / upper-body regions in the BGR frame.

        Returns:
            list of dicts: [
                {
                    "box": (x1, y1, x2, y2),
                    "confidence": float (0-100),
                    "centroid": (cx, cy),
                    "area": int,
                    "type": "HEAD"
                }
            ]
        """
        conf_threshold = conf_threshold if conf_threshold is not None else config.HEAD_CONFIDENCE_THRESHOLD
        if frame is None or frame.size == 0:
            return []

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        h, w = gray.shape

        head_boxes = []

        # 1. Upper Body / Head Region Detection
        if self.upperbody_cascade is not None and not self.upperbody_cascade.empty():
            bodies = self.upperbody_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(30, 30),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            for (bx, by, bw, bh) in bodies:
                # Top portion of upperbody is estimated to be the head region
                hx1, hy1 = bx, by
                hx2, hy2 = bx + bw, by + int(bh * 0.55)
                cx = int((hx1 + hx2) / 2)
                cy = int((hy1 + hy2) / 2)
                area = int((hx2 - hx1) * (hy2 - hy1))
                head_boxes.append({
                    "box": (hx1, hy1, hx2, hy2),
                    "confidence": round(max(conf_threshold, 0.45) * 100, 1),
                    "centroid": (cx, cy),
                    "area": area,
                    "type": "HEAD"
                })

        # 2. Profile Face / Head Angle Detection
        if self.profile_cascade is not None and not self.profile_cascade.empty():
            profiles = self.profile_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(24, 24)
            )
            for (px, py, pw, ph) in profiles:
                cx = int(px + pw / 2)
                cy = int(py + ph / 2)
                area = int(pw * ph)
                head_boxes.append({
                    "box": (px, py, px + pw, py + ph),
                    "confidence": round(max(conf_threshold, 0.40) * 100, 1),
                    "centroid": (cx, cy),
                    "area": area,
                    "type": "HEAD"
                })

        return head_boxes
