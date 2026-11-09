"""
detection_fusion.py — VisionGuard Multi-Level Detection Fusion Engine
Fuses YOLOv8 person detections, head detections, and face detections using spatial IoU,
containment matching, and non-maximum suppression (NMS) to output exact unique visible people.
"""

import numpy as np

def compute_iou(box1, box2):
    """
    Compute Intersection over Union (IoU) between box1 and box2.
    box = (x1, y1, x2, y2)
    """
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0, box1[2] - box1[0]) * max(0, box1[3] - box1[1])
    area2 = max(0, box2[2] - box2[0]) * max(0, box2[3] - box2[1])

    union_area = area1 + area2 - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area

def compute_ioa(boxA, boxB):
    """
    Compute Intersection over Area of Box B (IoA_B).
    Returns ratio of intersection area relative to boxB's area.
    Useful when boxB (e.g. head/face) is contained inside boxA (person).
    """
    x1 = max(boxA[0], boxB[0])
    y1 = max(boxA[1], boxB[1])
    x2 = min(boxA[2], boxB[2])
    y2 = min(boxA[3], boxB[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    inter_area = inter_w * inter_h

    areaB = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])
    if areaB <= 0:
        return 0.0
    return inter_area / areaB

def is_centroid_inside(box_inner, box_outer, top_fraction=1.0):
    """
    Check if the center point of box_inner is inside box_outer
    (optionally restricted to top_fraction of box_outer).
    """
    cx = (box_inner[0] + box_inner[2]) / 2.0
    cy = (box_inner[1] + box_inner[3]) / 2.0

    ox1, oy1, ox2, oy2 = box_outer
    outer_h = oy2 - oy1
    effective_oy2 = oy1 + outer_h * top_fraction

    return (ox1 <= cx <= ox2) and (oy1 <= cy <= effective_oy2)

class DetectionFusionEngine:
    def __init__(self, iou_thresh=0.35, ioa_thresh=0.40):
        self.iou_thresh = iou_thresh
        self.ioa_thresh = ioa_thresh

    def fuse_detections(self, person_dets, head_dets, face_dets):
        """
        Fuses multi-level detections (Person, Head, Face) into a list of UNIQUE people.

        Args:
            person_dets: list of dicts with keys ['box', 'confidence', 'track_id', ...]
            head_dets:   list of dicts with keys ['box', 'confidence', ...]
            face_dets:   list of dicts with keys ['box', 'confidence', ...]

        Returns:
            fused_persons: list of dicts representing unique individuals:
                [
                    {
                        "box": (x1, y1, x2, y2),
                        "confidence": float,
                        "centroid": (cx, cy),
                        "area": int,
                        "track_id": int/None,
                        "class_id": 0,
                        "class_name": "person",
                        "detection_source": "PERSON" / "HEAD" / "FACE" / "FUSED",
                        "components": {
                            "person_box": (x1, y1, x2, y2) or None,
                            "head_box": (x1, y1, x2, y2) or None,
                            "face_box": (x1, y1, x2, y2) or None
                        },
                        "is_weapon": False
                    }
                ]
        """
        person_dets = person_dets or []
        head_dets = head_dets or []
        face_dets = face_dets or []

        matched_heads = set()
        matched_faces = set()
        candidate_persons = []

        # 1. Match Person Detections with Heads and Faces
        for p in person_dets:
            p_box = p["box"]
            p_conf = p.get("confidence", 50.0)
            p_track_id = p.get("track_id", None)

            assoc_head = None
            assoc_face = None

            # Find overlapping head
            for i, h in enumerate(head_dets):
                if i in matched_heads:
                    continue
                h_box = h["box"]
                ioa = compute_ioa(p_box, h_box)
                iou = compute_iou(p_box, h_box)
                inside = is_centroid_inside(h_box, p_box, top_fraction=0.65)
                if ioa >= self.ioa_thresh or iou >= self.iou_thresh or inside:
                    matched_heads.add(i)
                    assoc_head = h_box
                    break

            # Find overlapping face
            for j, f in enumerate(face_dets):
                if j in matched_faces:
                    continue
                f_box = f["box"]
                ioa = compute_ioa(p_box, f_box)
                iou = compute_iou(p_box, f_box)
                inside = is_centroid_inside(f_box, p_box, top_fraction=0.55)
                if ioa >= self.ioa_thresh or iou >= self.iou_thresh or inside:
                    matched_faces.add(j)
                    assoc_face = f_box
                    break

            source = "FUSED" if (assoc_head or assoc_face) else "PERSON"
            cx = int((p_box[0] + p_box[2]) / 2)
            cy = int((p_box[1] + p_box[3]) / 2)
            area = int((p_box[2] - p_box[0]) * (p_box[3] - p_box[1]))

            candidate_persons.append({
                "box": p_box,
                "confidence": p_conf,
                "centroid": (cx, cy),
                "area": area,
                "track_id": p_track_id,
                "class_id": 0,
                "class_name": "person",
                "detection_source": source,
                "components": {
                    "person_box": p_box,
                    "head_box": assoc_head,
                    "face_box": assoc_face
                },
                "is_weapon": False
            })

        # 2. Match Unmatched Heads with Faces or create Head-Only Persons
        for i, h in enumerate(head_dets):
            if i in matched_heads:
                continue
            h_box = h["box"]
            h_conf = h.get("confidence", 40.0)

            assoc_face = None
            for j, f in enumerate(face_dets):
                if j in matched_faces:
                    continue
                f_box = f["box"]
                ioa = compute_ioa(h_box, f_box)
                iou = compute_iou(h_box, f_box)
                inside = is_centroid_inside(f_box, h_box, top_fraction=1.0)
                if ioa >= self.ioa_thresh or iou >= self.iou_thresh or inside:
                    matched_faces.add(j)
                    assoc_face = f_box
                    break

            matched_heads.add(i)

            hx1, hy1, hx2, hy2 = h_box
            hw = hx2 - hx1
            hh = hy2 - hy1
            syn_y2 = hy2 + int(hh * 1.5)
            syn_box = (hx1, hy1, hx2, syn_y2)

            cx = int((hx1 + hx2) / 2)
            cy = int((hy1 + hy2) / 2)
            area = int((hx2 - hx1) * (hy2 - hy1))

            candidate_persons.append({
                "box": syn_box,
                "confidence": h_conf,
                "centroid": (cx, cy),
                "area": area,
                "track_id": None,
                "class_id": 0,
                "class_name": "person",
                "detection_source": "HEAD",
                "components": {
                    "person_box": None,
                    "head_box": h_box,
                    "face_box": assoc_face
                },
                "is_weapon": False
            })

        # 3. Create Face-Only Persons for remaining unmatched faces
        for j, f in enumerate(face_dets):
            if j in matched_faces:
                continue
            f_box = f["box"]
            f_conf = f.get("confidence", 35.0)
            matched_faces.add(j)

            fx1, fy1, fx2, fy2 = f_box
            fw = fx2 - fx1
            fh = fy2 - fy1
            syn_y2 = fy2 + int(fh * 2.0)
            syn_box = (fx1, fy1, fx2, syn_y2)

            cx = int((fx1 + fx2) / 2)
            cy = int((fy1 + fy2) / 2)
            area = int(fw * fh)

            candidate_persons.append({
                "box": syn_box,
                "confidence": f_conf,
                "centroid": (cx, cy),
                "area": area,
                "track_id": None,
                "class_id": 0,
                "class_name": "person",
                "detection_source": "FACE",
                "components": {
                    "person_box": None,
                    "head_box": None,
                    "face_box": f_box
                },
                "is_weapon": False
            })

        # 4. Non-Maximum Suppression (NMS) to eliminate duplicate person candidates
        fused_persons = self._apply_nms(candidate_persons)
        return fused_persons

    def _apply_nms(self, candidates):
        if not candidates:
            return []

        def sort_key(c):
            type_score = 3 if c["detection_source"] in ("PERSON", "FUSED") else (2 if c["detection_source"] == "HEAD" else 1)
            return (c["confidence"], type_score)

        sorted_cand = sorted(candidates, key=sort_key, reverse=True)
        keep = []

        while sorted_cand:
            current = sorted_cand.pop(0)
            keep.append(current)

            remaining = []
            for other in sorted_cand:
                curr_box = current["components"]["person_box"] or current["box"]
                other_box = other["components"]["person_box"] or other["box"]

                iou = compute_iou(curr_box, other_box)
                ioa = compute_ioa(curr_box, other_box)

                h_iou = 0.0
                if current["components"]["head_box"] and other["components"]["head_box"]:
                    h_iou = compute_iou(current["components"]["head_box"], other["components"]["head_box"])

                if iou >= self.iou_thresh or ioa >= 0.70 or h_iou >= 0.50:
                    continue
                remaining.append(other)

            sorted_cand = remaining

        return keep
