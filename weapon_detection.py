"""
weapon_detection.py — Vision Guard Weapon Detection Module
Uses a custom-trained YOLO model if available.
Gracefully disabled if model is absent — never shows fake detections.
"""

import builtins
_orig_delattr = builtins.delattr
def _safe_delattr(obj, name):
    try:
        _orig_delattr(obj, name)
    except AttributeError:
        pass
builtins.delattr = _safe_delattr

import cv2
import os
import config

_weapon_model  = None
_model_missing = False


def _load_weapon_model():
    global _weapon_model, _model_missing
    if _model_missing:
        return False
    if _weapon_model is not None:
        return True
    if not os.path.exists(config.MODEL_WEAPON):
        print(f"[Weapon] Custom model not found at {config.MODEL_WEAPON}. "
              "Weapon detection DISABLED.")
        _model_missing = True
        return False
    try:
        from ultralytics import YOLO
        _weapon_model = YOLO(config.MODEL_WEAPON)
        print("[Weapon] Custom weapon model loaded.")
        return True
    except Exception as e:
        print(f"[Weapon] Failed to load weapon model: {e}. Weapon detection DISABLED.")
        _model_missing = True
        return False


class WeaponDetector:
    """Detects weapons using a custom YOLO model if available."""

    def __init__(self):
        self._available = _load_weapon_model()

    def detect(self, frame, inject_simulation: bool = False) -> dict:
        """
        Detect weapons in frame.

        Returns dict:
          available, detected, weapons (list), score (0-100)
        """
        if inject_simulation:
            return {
                "available": True,
                "detected":  True,
                "weapons":   [{"label": "Firearm (Simulated)",
                               "confidence": 90.0,
                               "box": (50, 50, 200, 200)}],
                "score":     90.0,
            }

        if not self._available:
            return {"available": False, "detected": False,
                    "weapons": [], "score": 0.0}

        weapons = []
        try:
            results = _weapon_model.predict(
                frame, conf=0.45, verbose=False
            )
            if results and results[0].boxes is not None:
                for box in results[0].boxes:
                    cls_id = int(box.cls[0])
                    score  = float(box.conf[0]) * 100
                    label  = (_weapon_model.names.get(cls_id, f"class_{cls_id}")
                              if hasattr(_weapon_model, "names") else f"class_{cls_id}")
                    xyxy   = box.xyxy[0].cpu().numpy().astype(int)
                    weapons.append({
                        "label":      label,
                        "confidence": round(score, 1),
                        "box":        tuple(xyxy),
                    })
                    # Draw on frame
                    x1, y1, x2, y2 = xyxy
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(frame, f"{label} {score:.0f}%",
                                (x1, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX,
                                0.5, (0, 0, 255), 2)
        except Exception as e:
            print(f"[Weapon] Inference error: {e}")

        top_score = max((w["confidence"] for w in weapons), default=0.0)
        return {
            "available": True,
            "detected":  len(weapons) > 0,
            "weapons":   weapons,
            "score":     top_score,
        }
