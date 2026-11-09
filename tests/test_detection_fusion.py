"""
test_detection_fusion.py — Unit Tests for Multi-Level Detection & Fusion Engine
Verifies all 7 required crowd detection test cases specified in VisionGuard requirements.
"""

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from detection_fusion import DetectionFusionEngine, compute_iou, compute_ioa, is_centroid_inside


class TestDetectionFusion(unittest.TestCase):

    def setUp(self):
        self.fusion = DetectionFusionEngine(iou_thresh=0.35, ioa_thresh=0.40)

    def test_case_1_full_body_person(self):
        """TEST 1: Full-body person alone -> Final count = 1"""
        person_dets = [{"box": (100, 100, 200, 400), "confidence": 85.0, "track_id": 1}]
        head_dets = []
        face_dets = []

        result = self.fusion.fuse_detections(person_dets, head_dets, face_dets)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["detection_source"], "PERSON")

    def test_case_2_head_only_person(self):
        """TEST 2: Head-only person visible -> Final count = 1"""
        person_dets = []
        head_dets = [{"box": (120, 100, 180, 160), "confidence": 75.0}]
        face_dets = []

        result = self.fusion.fuse_detections(person_dets, head_dets, face_dets)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["detection_source"], "HEAD")

    def test_case_3_face_only_person(self):
        """TEST 3: Face-only visible person -> Final count = 1"""
        person_dets = []
        head_dets = []
        face_dets = [{"box": (130, 110, 170, 150), "confidence": 70.0}]

        result = self.fusion.fuse_detections(person_dets, head_dets, face_dets)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["detection_source"], "FACE")

    def test_case_4_full_body_head_face_same_person(self):
        """TEST 4: Full-body + head + face of the SAME person -> Final count = 1 (NOT 3)"""
        person_dets = [{"box": (100, 100, 200, 400), "confidence": 90.0, "track_id": 1}]
        # Head is inside the top region of the person box
        head_dets = [{"box": (120, 110, 180, 170), "confidence": 80.0}]
        # Face is inside the head & top region of person box
        face_dets = [{"box": (130, 120, 170, 160), "confidence": 75.0}]

        result = self.fusion.fuse_detections(person_dets, head_dets, face_dets)
        self.assertEqual(len(result), 1, "Must suppress duplicate head and face detections for the same person!")
        self.assertEqual(result[0]["detection_source"], "FUSED")

    def test_case_5_two_people_close_together(self):
        """TEST 5: Two people standing close together -> Final count = 2"""
        person1 = {"box": (100, 100, 200, 400), "confidence": 88.0, "track_id": 1}
        person2 = {"box": (210, 100, 310, 400), "confidence": 85.0, "track_id": 2}
        person_dets = [person1, person2]
        head_dets = []
        face_dets = []

        result = self.fusion.fuse_detections(person_dets, head_dets, face_dets)
        self.assertEqual(len(result), 2)

    def test_case_6_dense_crowd(self):
        """TEST 6: Dense crowd with mixed person, head, and face detections -> Unique count"""
        p1 = {"box": (50, 100, 120, 350), "confidence": 85.0}
        h1 = {"box": (60, 105, 110, 160), "confidence": 75.0}

        h2 = {"box": (150, 110, 200, 165), "confidence": 70.0}

        f3 = {"box": (250, 115, 290, 155), "confidence": 65.0}

        p4 = {"box": (320, 100, 400, 350), "confidence": 90.0}

        person_dets = [p1, p4]
        head_dets = [h1, h2]
        face_dets = [f3]

        result = self.fusion.fuse_detections(person_dets, head_dets, face_dets)
        self.assertEqual(len(result), 4, "Dense crowd must correctly count 4 unique individuals!")

    def test_case_7_partially_occluded_person(self):
        """TEST 7: Partially occluded person (head/upper body visible) -> Retains individual count = 1"""
        person_dets = []
        head_dets = [{"box": (200, 150, 280, 230), "confidence": 78.0}]
        face_dets = [{"box": (220, 165, 260, 210), "confidence": 72.0}]

        result = self.fusion.fuse_detections(person_dets, head_dets, face_dets)
        self.assertEqual(len(result), 1, "Partially occluded person must be retained as 1 unique person!")


if __name__ == "__main__":
    unittest.main()
