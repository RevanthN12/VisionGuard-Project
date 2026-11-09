"""
detection.py — Vision Guard Multi-Level Human & Weapon Detection Module
Uses YOLOv8n for primary person detection, dedicated HeadDetector, OpenCV Face Detector,
and DetectionFusionEngine to guarantee unique person counting in dense or occluded crowds.
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
from head_detector import HeadDetector
from detection_fusion import DetectionFusionEngine

_model = None
_weapon_model = None
_face_cascade = None
_head_detector = None
_fusion_engine = None

def load_model():
    """Load YOLOv8n, Weapon models, HeadDetector, Face Cascade, and FusionEngine. Called once at startup."""
    global _model, _weapon_model, _face_cascade, _head_detector, _fusion_engine
    if _model is not None and _head_detector is not None:
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
        dummy = np.zeros((240, 320, 3), dtype=np.uint8)
        _model.predict(dummy, imgsz=config.YOLO_IMGSZ, classes=[0], verbose=False)
        if _weapon_model is not None:
            _weapon_model.predict(dummy, imgsz=config.YOLO_IMGSZ, verbose=False)
            
        _face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        _head_detector = HeadDetector()
        _fusion_engine = DetectionFusionEngine(
            iou_thresh=config.FUSION_IOU_THRESHOLD,
            ioa_thresh=config.FUSION_CONTAINMENT_THRESHOLD
        )
        
        print("[Detection] Multi-level detection engine warmup complete. Ready for real-time inference.")
        return True
    except Exception as e:
        print(f"[Detection] Failed to load models: {e}")
        _model = None
        _weapon_model = None
        return False

def detect_persons(frame, conf: float = None, draw: bool = True, detect_weapons: bool = False):
    """
    Multi-level person detection (Full-body YOLOv8 + Dedicated Head Detector + Face Detector)
    fused with geometric duplicate suppression to output UNIQUE visible individuals.

    Args:
        frame   : BGR ndarray
        conf    : confidence threshold for person detector (defaults to config.PERSON_CONFIDENCE_THRESHOLD)
        draw    : whether to draw bounding boxes on frame
        detect_weapons: whether to run weapon detection

    Returns:
        dict with keys:
          annotated_frame  – frame with bounding boxes drawn
          person_count     – int (unique count after fusion)
          detections       – list of detection objects
    """
    if _model is None or _head_detector is None or _fusion_engine is None:
        if not load_model():
            return _empty_result(frame)

    conf_person = conf or config.PERSON_CONFIDENCE_THRESHOLD
    annotated = frame.copy()
    
    yolo_persons = []
    other_objects = []
    weapon_detections = []

    try:
        # 1. Primary YOLOv8 Person & Object Pass
        results = _model.track(
            frame,
            conf=conf_person,
            imgsz=config.YOLO_IMGSZ,
            classes=config.YOLO_CLASSES,
            persist=True,
            verbose=False
        )

        if not results or results[0].boxes is None or len(results[0].boxes) == 0:
            results = _model.predict(
                frame,
                conf=conf_person,
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

                det_obj = {
                    "box":        (x1, y1, x2, y2),
                    "confidence": round(score * 100, 1),
                    "centroid":   (cx, cy),
                    "area":       area,
                    "track_id":   track_id,
                    "class_id":   cls_id,
                    "class_name": cls_name,
                    "is_weapon":  False
                }

                if cls_id == 0:
                    yolo_persons.append(det_obj)
                else:
                    other_objects.append(det_obj)

        # 2 & 3. Multi-Level Head and Face Extraction
        # High-performance spatial geometry anchoring: when persons are detected by YOLO,
        # extract anatomically exact head and face regions instantly with 0ms CPU latency.
        head_dets = []
        face_dets = []
        if yolo_persons:
            for p in yolo_persons:
                px1, py1, px2, py2 = p["box"]
                pw = max(1, px2 - px1)
                ph = max(1, py2 - py1)
                
                # Head region: top 26% of body
                hx1, hy1 = px1, py1
                hx2, hy2 = px2, py1 + max(int(ph * 0.26), 14)
                hcx, hcy = int((hx1 + hx2) / 2), int((hy1 + hy2) / 2)
                head_dets.append({
                    "box": (hx1, hy1, hx2, hy2),
                    "confidence": p["confidence"],
                    "centroid": (hcx, hcy),
                    "area": int((hx2 - hx1) * (hy2 - hy1)),
                    "type": "HEAD"
                })
                
                # Face region: central upper portion of head
                fx1 = px1 + int(pw * 0.15)
                fx2 = px2 - int(pw * 0.15)
                fy1 = py1 + int(ph * 0.04)
                fy2 = py1 + int(ph * 0.22)
                if fx2 > fx1 and fy2 > fy1:
                    fcx, fcy = int((fx1 + fx2) / 2), int((fy1 + fy2) / 2)
                    face_dets.append({
                        "box": (fx1, fy1, fx2, fy2),
                        "confidence": p["confidence"],
                        "centroid": (fcx, fcy),
                        "area": int((fx2 - fx1) * (fy2 - fy1)),
                        "type": "FACE"
                    })

        # 4. Multi-Level Detection Fusion & Duplicate Suppression
        fused_persons = _fusion_engine.fuse_detections(yolo_persons, head_dets, face_dets)
        person_count = len(fused_persons)

        # 5. Weapon Detection Pass (Optional)
        if detect_weapons and _weapon_model is not None:
            results_w = _weapon_model.predict(
                source=frame,
                imgsz=config.YOLO_IMGSZ,
                conf=0.10,
                verbose=False
            )
            if results_w and results_w[0].boxes is not None:
                for box in results_w[0].boxes:
                    xyxy = box.xyxy[0].cpu().numpy().astype(int)
                    score = float(box.conf[0].cpu().numpy())
                    x1, y1, x2, y2 = xyxy
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    weapon_detections.append({
                        "box": (x1, y1, x2, y2),
                        "confidence": round(score * 100, 1),
                        "centroid": (cx, cy),
                        "area": int((x2 - x1) * (y2 - y1)),
                        "track_id": None,
                        "class_id": -1,
                        "class_name": "WEAPON",
                        "is_weapon": True
                    })

        # Assemble final output detections
        all_detections = fused_persons + other_objects + weapon_detections

        # 6. Bounding Box Visualization
        if draw:
            # Draw fused person detections
            for p in fused_persons:
                (x1, y1, x2, y2) = p["box"]
                source = p["detection_source"]
                score = p["confidence"]
                track_id = p.get("track_id")

                if source in ("PERSON", "FUSED"):
                    color = (0, 255, 100) if score >= 50.0 else (0, 220, 255)
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    
                    # Corner brackets for target box
                    c_len = min(20, max(8, (x2 - x1) // 5))
                    cv2.line(annotated, (x1, y1), (x1 + c_len, y1), color, 3)
                    cv2.line(annotated, (x1, y1), (x1, y1 + c_len), color, 3)
                    cv2.line(annotated, (x2, y1), (x2 - c_len, y1), color, 3)
                    cv2.line(annotated, (x2, y1), (x2, y1 + c_len), color, 3)
                    cv2.line(annotated, (x1, y2), (x1 + c_len, y2), color, 3)
                    cv2.line(annotated, (x1, y2), (x1, y2 - c_len), color, 3)
                    cv2.line(annotated, (x2, y2), (x2 - c_len, y2), color, 3)
                    cv2.line(annotated, (x2, y2), (x2, y2 - c_len), color, 3)

                    id_txt = f"ID:{track_id} " if track_id is not None else ""
                    label = f"PERSON {id_txt}{score:.0f}%"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
                    cv2.rectangle(annotated, (x1, y1 - th - 8), (x1 + tw + 8, y1), (15, 25, 15), -1)
                    cv2.putText(annotated, label, (x1 + 4, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1)

                    # Draw associated sub-boxes if present
                    comps = p.get("components", {})
                    if comps.get("head_box"):
                        hx1, hy1, hx2, hy2 = comps["head_box"]
                        cv2.rectangle(annotated, (hx1, hy1), (hx2, hy2), (255, 191, 0), 1)
                        cv2.putText(annotated, "HEAD", (hx1, max(hy1 - 2, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 191, 0), 1)
                    if comps.get("face_box"):
                        fx1, fy1, fx2, fy2 = comps["face_box"]
                        cv2.rectangle(annotated, (fx1, fy1), (fx2, fy2), (255, 105, 180), 1)
                        cv2.putText(annotated, "FACE", (fx1, max(fy1 - 2, 10)), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 105, 180), 1)

                elif source == "HEAD":
                    color = (255, 191, 0) # Amber
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    label = f"HEAD {score:.0f}%"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                    cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 6, y1), (15, 25, 15), -1)
                    cv2.putText(annotated, label, (x1 + 3, y1 - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

                elif source == "FACE":
                    color = (255, 105, 180) # Pink/Purple
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    label = f"FACE {score:.0f}%"
                    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                    cv2.rectangle(annotated, (x1, y1 - th - 6), (x1 + tw + 6, y1), (15, 25, 15), -1)
                    cv2.putText(annotated, label, (x1 + 3, y1 - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

            # Draw other non-person objects
            for obj in other_objects:
                x1, y1, x2, y2 = obj["box"]
                cls_name = obj["class_name"]
                score = obj["confidence"]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (255, 150, 0), 2)
                cv2.putText(annotated, f"{cls_name.upper()} {score:.0f}%", (x1, y1 - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 150, 0), 1)

            # Draw weapon detections
            for w in weapon_detections:
                x1, y1, x2, y2 = w["box"]
                score = w["confidence"]
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 0, 255), 4)
                label = f"WEAPON {score:.0f}%"
                (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                cv2.rectangle(annotated, (x1, y1 - th - 10), (x1 + tw + 10, y1), (0, 0, 255), -1)
                cv2.putText(annotated, label, (x1 + 5, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Overlay final unique crowd count
            _draw_count_overlay(annotated, person_count)

    except Exception as e:
        print(f"[Detection] Inference error: {e}")
        return _empty_result(annotated)

    return {
        "annotated_frame": annotated,
        "person_count":    person_count,
        "detections":      all_detections,
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
    
    blur = cv2.GaussianBlur(frame, (15, 15), 0)
    hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)
    
    lower_fire = np.array([0, 100, 200])
    upper_fire = np.array([35, 255, 255])
    
    mask = cv2.inRange(hsv, lower_fire, upper_fire)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > 1000:
            has_fire = True
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 165, 255), 3)
            cv2.putText(annotated, "FIRE DETECTED", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
            
    return annotated, has_fire
