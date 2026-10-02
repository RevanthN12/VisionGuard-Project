"""
test_api.py — Unit & Integration Tests for VisionGuard DevOps CI/CD
"""

import os
import sys
import unittest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import server
import risk_predictor
import evidence_recorder


class TestVisionGuardDevOps(unittest.TestCase):

    def setUp(self):
        server.app.config['TESTING'] = True
        self.client = server.app.test_client()

    def test_health_check_endpoint(self):
        """Test Kubernetes readiness/liveness health check endpoint."""
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("status"), "healthy")

    def test_metrics_endpoint(self):
        """Test Prometheus metrics exporter endpoint."""
        response = self.client.get('/metrics')
        self.assertEqual(response.status_code, 200)

    def test_risk_predictor_calculation(self):
        """Test Risk Predictor weighted score calculation."""
        predictor = risk_predictor.RiskPredictor()
        density_res = {"density_score": 50.0, "level": "MEDIUM"}
        movement_res = {"speed": 5.0, "level": "MEDIUM", "turbulence": 1.2}
        behavior_res = {"status": "NORMAL", "congestion_frames": 0}
        violence_res = {"detected": False}
        weapon_res = {"detected": False}

        risk = predictor.predict(density_res, movement_res, behavior_res, violence_res, weapon_res, people_count=10)
        self.assertIn("score", risk)
        self.assertIn("level", risk)
        self.assertGreaterEqual(risk["score"], 0)
        self.assertLessEqual(risk["score"], 100)

    def test_video_only_evidence_policy(self):
        """Verify that EvidenceRecorder strictly enforces video-only evidence (no permanent image snapshots)."""
        recorder = evidence_recorder.EvidenceRecorder()
        # maybe_save must return None to prevent image snapshot storage
        img_result = recorder.maybe_save(None, {}, {}, {}, 0)
        self.assertIsNone(img_result, "EvidenceRecorder must return None to enforce video-only evidence policy.")


if __name__ == "__main__":
    unittest.main()
