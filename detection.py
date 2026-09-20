"""
detection.py — Vision Guard Human & Weapon Detection Module
Uses YOLOv8n to detect persons/bags and weapon_best.pt to detect weapons.
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
import numpy as np
import os
import config

_model = None
_weapon_model = None

def load_model():
    """Load YOLOv8n and Weapon models. Called once at startup."""
    global _model, _weapon_model
    if _model is not None:
        return True
    try:
        from ultralytics import YOLO
        if not os.path.exists(config.MODEL_YOLO):
            print(f"[Detection] Model not found: {config.MODEL_YOLO}. Downloading…")
        _model = YOLO(config.MODEL_YOLO)
        
        if os.path.exists(config.MODEL_WEAPON):
            _weapon_model = YOLO(config.MODEL_WEAPON)
        else:
            print(f"[Detection] Weapon model not found at {config.MODEL_WEAPON}")
            
        print("[Detection] Models loaded successfully. Warming up inference engine...")
        # Pre-warm model in main thread to load torchvision and DLLs immediately
        dummy = np.zeros((240, 320, 3), dtype=np.uint8)
        _model.predict(dummy, imgsz=config.YOLO_IMGSZ, classes=[0], verbose=False)
        if _weapon_model is not None:
            _weapon_model.predict(dummy, imgsz=config.YOLO_IMGSZ, verbose=False)
        print("[Detection] Engine warmup complete. Ready for real-time inference.")
        return True
    except Exception as e:
        print(f"[Detection] Failed to load models: {e}")
        _model = None
        _weapon_model = None
        return False

def detect_persons(frame, conf: float = None, draw: bool = True, detect_weapons: bool = False):
    """
    Detect persons/bags (tracking) and optionally weapons.

    Args:
        frame   : BGR ndarray
        conf    : confidence threshold (defaults to config.YOLO_CONF)
        draw    : whether to draw boxes on frame
        detect_weapons: whether to run weapon detection

    Returns:
        dict with keys:
          annotated_frame  – frame with bounding boxes drawn
          person_count     – int
          detections       – list of {box, confidence, centroid, area, track_id, class_id, class_name, is_weapon}
    """
    if _model is None:
        if not load_model():
            return _empty_result(frame)

    conf = conf or config.YOLO_CONF
    annotated = frame.copy()
    detections = []

    try:
        # --- Main Tracking Pass (Native BGR frame into YOLO) ---
        results = _model.track(
            frame,
            conf=conf,
            imgsz=config.YOLO_IMGSZ,
            classes=config.YOLO_CLASSES,
            persist=True,
            verbose=False
        )

        # Fallback to direct prediction if tracker produced no boxes
        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            results = _model.predict(
                frame,
                conf=conf,
                imgsz=config.YOLO_IMGSZ,
                classes=config.YOLO_CLASSES,
                verbose=False
            )

        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                xyxy  = box.xyxy[0].cpu().numpy().astype(int)
                score = float(box.conf[0].cpu().numpy())
                cls_id = int(box.cls[0].cpu().numpy())
                cls_name = _model.names[cls_id] if hasattr(_model, 'names') else str(cls_id)
                
                track_id = None
                if box.id is not None:
                    track_id = int(box.id[0].cpu().numpy())

                x1, y1, x2, y2 = xyxy
                cx = int((x1 + x2) / 2)
                cy = int((y1 + y2) / 2)
                area = int((x2 - x1) * (y2 - y1))

                detections.append({
                    "box":        (x1, y1, x2, y2),
                    "confidence": round(score * 100, 1),
                    "centroid":   (cx, cy),
                    "area":       area,
                    "track_id":   track_id,
                    "class_id":   cls_id,
                    "class_name": cls_name,
                    "is_weapon":  False
                })

                if draw:
                    # Draw figure box based on class
                    if cls_id == 0:  # Person / Figure
                        color = (0, 255, 100) if score >= 0.50 else (0, 220, 255)
                        # Whole body / figure bounding box
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                        
                        # Corner accent brackets
                        c_len = min(20, max(8, (x2 - x1) // 5))
                        cv2.line(annotated, (x1, y1), (x1 + c_len, y1), color, 3)
                        cv2.line(annotated, (x1, y1), (x1, y1 + c_len), color, 3)
                        cv2.line(annotated, (x2, y1), (x2 - c_len, y1), color, 3)
                        cv2.line(annotated, (x2, y1), (x2, y1 + c_len), color, 3)
                        cv2.line(annotated, (x1, y2), (x1 + c_len, y2), color, 3)
                        cv2.line(annotated, (x1, y2), (x1, y2 - c_len), color, 3)
                        cv2.line(annotated, (x2, y2), (x2 - c_len, y2), color, 3)
                        cv2.line(annotated, (x2, y2), (x2, y2 - c_len), color, 3)

                        # Person figure label
                        id_txt = f"ID:{track_id} " if track_id is not None else ""
                        label = f"FIGURE {id_txt}{score*100:.0f}%"
                        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
                        cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 8, y1), (15, 25, 15), -1)
                        cv2.putText(annotated, label, (x1 + 4, y1 - 4),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1)

                        # Dedicated Face & Head Targeting Box (top 35% of person figure)
                        head_w = max(16, int((x2 - x1) * 0.50))
                        head_h = max(16, int((y2 - y1) * 0.35))
                        fx1 = max(0, cx - head_w // 2)
                        fx2 = min(annotated.shape[1], cx + head_w // 2)
                        fy1 = y1
                        fy2 = min(annotated.shape[0], y1 + head_h)
                        face_color = (0, 240, 255) # Cyan for face
                        cv2.rectangle(annotated, (fx1, fy1), (fx2, fy2), face_color, 1)
                        # Face corner brackets
                        fc_len = max(5, head_w // 4)
                        cv2.line(annotated, (fx1, fy1), (fx1 + fc_len, fy1), face_color, 2)
                        cv2.line(annotated, (fx1, fy1), (fx1, fy1 + fc_len), face_color, 2)
                        cv2.line(annotated, (fx2, fy1), (fx2 - fc_len, fy1), face_color, 2)
                        cv2.line(annotated, (fx2, fy1), (fx2, fy1 + fc_len), face_color, 2)
                        cv2.line(annotated, (fx1, fy2), (fx1 + fc_len, fy2), face_color, 2)
                        cv2.line(annotated, (fx1, fy2), (fx1, fy2 - fc_len), face_color, 2)
                        cv2.line(annotated, (fx2, fy2), (fx2 - fc_len, fy2), face_color, 2)
                        cv2.line(annotated, (fx2, fy2), (fx2, fy2 - fc_len), face_color, 2)
                        
                        # Face center crosshair
                        fcx, fcy = (fx1 + fx2) // 2, (fy1 + fy2) // 2
                        cv2.drawMarker(annotated, (fcx, fcy), face_color, cv2.MARKER_CROSS, 8, 1)
                        cv2.putText(annotated, "FACE TARGET", (fx1, fy2 + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.36, face_color, 1)
                    else:  # Bags / Objects
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 150, 0), 2)
                        cv2.putText(annotated, f"{cls_name.upper()} {score*100:.0f}%", (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 150, 0), 1)

        # --- Weapon Detection Pass ---
        if detect_weapons and _weapon_model is not None:
            results_w = _weapon_model.predict(
                source=frame,
                imgsz=config.YOLO_IMGSZ,
                conf=0.25,
                verbose=False
            )
            
            if results_w and results_w[0].boxes is not None:
                for box in results_w[0].boxes:
                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    score = float(box.conf[0].cpu().numpy())
                    x1, y1, x2, y2 = xyxy
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    
                    detections.append({
                        "box": (x1, y1, x2, y2),
                        "confidence": round(score * 100, 1),
                        "centroid": (cx, cy),
                        "area": int((x2 - x1) * (y2 - y1)),
                        "track_id": None,
                        "class_id": -1,
                        "class_name": "WEAPON",
                        "is_weapon": True
                    })
                    
                    if draw:
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 4)
                        label = f"WEAPON {score*100:.0f}%"
                        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                        cv2.rectangle(annotated, (x1, y1 - th - 10), (x1 + tw + 10, y1), (0, 0, 255), -1)
                        cv2.putText(annotated, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Person count overlay & AI targeting HUD
        person_count = sum(1 for d in detections if d["class_id"] == 0)
        if draw:
            _draw_count_overlay(annotated, person_count)

    except Exception as e:
        print(f"[Detection] Inference error: {e}")
        return _empty_result(annotated)

    return {
        "annotated_frame": annotated,
        "person_count":    person_count,
        "detections":      detections,
    }

def _draw_count_overlay(frame, count):
    h, w = frame.shape[:2]
    label = f"People: {count}"
    cv2.rectangle(frame, (w - 140, 8), (w - 6, 34), (15, 15, 20), -1)
    cv2.putText(frame, label, (w - 134, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 150), 2)

def _empty_result(frame):
    return {
        "annotated_frame": frame,
        "person_count":    0,
        "detections":      [],
    }

def detect_fire(frame):
    """
    Heuristic fire detection using OpenCV HSV color masking.
    Returns (annotated_frame, has_fire)
    """
    annotated = frame.copy()
    has_fire = False
    
    # Blur to reduce noise
    blur = cv2.GaussianBlur(frame, (15, 15), 0)
    hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
    
    # Define range for fire colors (bright yellow, orange, red)
    lower_fire = np.array([0, 100, 200])
    upper_fire = np.array([35, 255, 255])
    
    mask = cv2.inRange(hsv, lower_fire, upper_fire)
    
    # Find contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1000: # Significant size
            has_fire = True
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 165, 255), 3) # Orange box
            cv2.putText(annotated, "FIRE DETECTED", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            
    return annotated, has_fire
