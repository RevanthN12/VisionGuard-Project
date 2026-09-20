"""
risk_predictor.py — Vision Guard Stampede Risk Prediction Module
Weighted multi-modal risk formula. Upgraded to support ML models.

Levels:
  0–29   → SAFE
  30–49  → CAUTION
  50–69  → WARNING
  70–84  → HIGH RISK
  85–100 → CRITICAL
"""

import os
import joblib
import numpy as np
import config
from collections import deque

# ── Level constants ───────────────────────────────────────────────────────────
LEVEL_SAFE      = "SAFE"
LEVEL_CAUTION   = "CAUTION"
LEVEL_WARNING   = "WARNING"
LEVEL_HIGH      = "HIGH RISK"
LEVEL_CRITICAL  = "CRITICAL"

LEVEL_COLORS = {
    LEVEL_SAFE:     "#22C55E",
    LEVEL_CAUTION:  "#EAB308",
    LEVEL_WARNING:  "#F97316",
    LEVEL_HIGH:     "#EF4444",
    LEVEL_CRITICAL: "#7C3AED",
    "HIGH_RISK":    "#EF4444",
}

LEVEL_ICONS = {
    LEVEL_SAFE:     "✅",
    LEVEL_CAUTION:  "⚠️",
    LEVEL_WARNING:  "🚨",
    LEVEL_HIGH:     "🔴",
    LEVEL_CRITICAL: "💀",
    "HIGH_RISK":    "🔴",
}

# Calibrated guidance statements reflecting visual indicator assessments
RECOMMENDED_ACTIONS = {
    LEVEL_SAFE:     "Routine surveillance active. Observed visual indicators indicate normal crowd behavior.",
    LEVEL_CAUTION:  "Moderate crowd presence observed. Movement flow remains stable; maintain surveillance.",
    LEVEL_WARNING:  "Elevated crowd density or dynamic movement detected. Potential congestion developing.",
    LEVEL_HIGH:     "High stampede risk / potential dangerous crowd behavior indicated. Deploy crowd control team.",
    LEVEL_CRITICAL: "CRITICAL: Immediate crowd crush or security threat hazard indicated. Initiate emergency protocol.",
    "HIGH_RISK":    "High stampede risk / potential dangerous crowd behavior indicated. Deploy crowd control team.",
}

# Probability mapping for trained ML model
CLASS_WEIGHT_VALUES = {
    "SAFE":      18.0,
    "CAUTION":   42.0,
    "WARNING":   62.0,
    "HIGH_RISK": 78.0,
    "HIGH RISK": 78.0,
    "CRITICAL":  94.0,
}


class RiskPredictor:
    """
    Adaptive Multi-Modal Crowd Risk Assessment Engine.
    Dynamically models crowd scale, flow velocity, turbulence, congestion accumulation,
    behavioral anomalies, and physical threats without fixed step thresholds.
    """

    def __init__(self):
        self._risk_hist = deque(maxlen=60)
        self._smoothed_score = 0.0
        self._sustained_elevated_frames = 0
        
        # Weights for baseline fusion (sum to 1.0)
        self._w = {
            "density":    config.RISK_W_DENSITY,
            "movement":   config.RISK_W_MOVEMENT,
            "behavior":   config.RISK_W_BEHAVIOR,
            "congestion": config.RISK_W_CONGESTION,
            "threat":     config.RISK_W_THREAT,
        }
        
        # ML Model
        self.model = None
        self.prediction_mode = "ADAPTIVE REAL-TIME"
        self._load_model()

    def _load_model(self):
        """Loads trained Random Forest model if available."""
        model_path = os.path.join("models", "stampede_risk_model.joblib")
        if os.path.exists(model_path):
            try:
                self.model = joblib.load(model_path)
                self.prediction_mode = "TRAINED ML + ADAPTIVE"
                print(f"[RiskPredictor] Loaded ML model from {model_path}")
            except Exception as e:
                print(f"[RiskPredictor] ML model load failed: {e}. Using Adaptive Real-Time Engine.")
                self.model = None
                self.prediction_mode = "ADAPTIVE REAL-TIME"
        else:
            self.model = None
            self.prediction_mode = "ADAPTIVE REAL-TIME"

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(self,
                density_result:  dict,
                movement_result: dict,
                behavior_result: dict,
                violence_result: dict = None,
                weapon_result:   dict = None,
                people_count:    int = 0) -> dict:
        """
        Compute continuous real-time crowd risk from multi-modal sensor inputs.
        Evaluates scale, flow velocity, turbulence, congestion, behavior, and threats.
        """
        # 1. Extract component scores (0 - 100)
        d_score    = float(density_result.get("density_score", 0.0))
        d_pct      = float(density_result.get("density_pct", 0.0))
        crowd_sc   = float(density_result.get("crowd_scale", min(people_count / 15.0, 1.0) if people_count > 1 else 0.12 if people_count == 1 else 0.0))
        
        m_score    = float(movement_result.get("score", 0.0))
        m_speed    = float(movement_result.get("speed", 0.0))
        m_turb     = float(movement_result.get("turbulence", 0.0))
        m_accel    = float(movement_result.get("acceleration", 0.0))
        is_panic   = bool(movement_result.get("is_panic", False))

        b_score    = float(behavior_result.get("score", 0.0))
        cong_f     = int(behavior_result.get("congestion_frames", 0))
        cong_s     = min((cong_f / max(config.CONGESTION_FRAMES, 1)) * 100.0, 100.0)

        v_score    = float(violence_result.get("score", 0.0)) if violence_result else 0.0
        v_detected = bool(violence_result.get("detected", False)) if violence_result else False

        w_detected = bool(weapon_result.get("detected", False)) if weapon_result else False
        w_score    = 100.0 if w_detected else float(weapon_result.get("score", 0.0)) if weapon_result else 0.0

        # Physical threat signal (weapons / violent altercation)
        threat_s   = min(v_score * 0.5 + w_score * 0.5, 100.0)
        if w_detected:
            threat_s = 100.0
        elif v_detected:
            threat_s = max(threat_s, 85.0)

        # 2. Compute ML probability distribution if model available
        ml_score = None
        ml_confidence = 100.0
        if self.model is not None:
            features = np.array([[
                people_count,
                d_score,
                m_score,
                b_score,
                cong_s,
                v_score,
                w_score
            ]])
            try:
                probs = self.model.predict_proba(features)[0]
                classes = self.model.classes_
                # Compute smooth probability-weighted score
                weighted_sum = 0.0
                for c, p in zip(classes, probs):
                    weighted_sum += p * CLASS_WEIGHT_VALUES.get(c, 20.0)
                ml_score = float(weighted_sum)
                ml_confidence = float(np.max(probs)) * 100.0
            except Exception as ex:
                ml_score = None

        # Dynamically scale down movement score contribution if crowd scale is extremely low
        # This prevents full-frame optical flow camera noise from driving the score up when only 0-2 people are present
        if crowd_sc < 0.15:
            m_score = m_score * 0.2
        elif crowd_sc < 0.3:
            m_score = m_score * 0.5

        # 3. Dynamic Physics & Behavioral Fusion
        # ── Weighted Linear Baseline ──────────────────────────────────────────
        raw_baseline = (
            d_score  * self._w["density"]    +
            m_score  * self._w["movement"]   +
            b_score  * self._w["behavior"]   +
            cong_s   * self._w["congestion"] +
            threat_s * self._w["threat"]
        )

        # ── Synergistic Stampede & Chaos Factor ────────────────────────────────
        # Stampede hazard emerges when High Density is coupled with High Speed & Chaos
        speed_norm = min(m_speed / config.MOVE_PANIC, 1.0)
        turb_norm  = min(m_turb / 8.0, 1.0)
        accel_norm = min(abs(m_accel) / 3.5, 1.0)

        # Dynamic crowd stampede interaction (scaled by actual crowd presence)
        stampede_synergy = (d_pct * 0.5 + crowd_sc * 0.5) * (speed_norm * 0.55 + turb_norm * 0.45) * 35.0
        if is_panic and crowd_sc > 0.3:
            stampede_synergy += 20.0

        # ── Congestion Buildup with Low Movement ──────────────────────────────
        # When crowd is packed and stationary/trapped over time
        crowd_trap_factor = 0.0
        if cong_s > 30.0 and crowd_sc > 0.3:
            crowd_trap_factor = (cong_s / 100.0) * crowd_sc * 18.0

        # ── Orderly Crowd Moderation ──────────────────────────────────────────
        # A large crowd moving calmly and coherently is not in stampede danger.
        orderly_moderation = 0.0
        if crowd_sc > 0.4 and speed_norm < 0.35 and turb_norm < 0.30 and threat_s < 30.0:
            orderly_moderation = -12.0 * (1.0 - speed_norm) * (1.0 - turb_norm)

        # ── Single Person & Small Group Regularization ────────────────────────
        # 1 or 2 people moving normally cannot cause a crowd stampede.
        small_group_moderation = 0.0
        if people_count <= 2 and threat_s < 45.0:
            # Dampen any optical-flow noise or close-proximity camera occupancy heavily
            small_group_moderation = -45.0

        # Combine dynamic physical components
        fused_raw = raw_baseline + stampede_synergy + crowd_trap_factor + orderly_moderation + small_group_moderation

        # Threat override for genuine armed weapon or physical altercation
        if threat_s >= 85.0:
            fused_raw = max(fused_raw, 88.0)
        elif threat_s >= 50.0:
            fused_raw = max(fused_raw, 65.0)

        # Blend with ML model prediction if available
        if ml_score is not None:
            fused_raw = 0.65 * fused_raw + 0.35 * ml_score

        raw_score = float(np.clip(fused_raw, 0.0, 100.0))

        # 4. Temporal Exponential Moving Average (EMA) Smoothing
        # Filters momentary 1-frame spikes while responding to sustained escalations
        alpha = 0.25
        if len(self._risk_hist) == 0:
            self._smoothed_score = raw_score
        else:
            self._smoothed_score = alpha * raw_score + (1.0 - alpha) * self._smoothed_score

        self._risk_hist.append(self._smoothed_score)
        smoothed = round(float(self._smoothed_score), 1)

        # 5. Classify Risk Level
        level = self._classify(smoothed)
        display_level = "HIGH RISK" if level in ("HIGH RISK", "HIGH_RISK") else level

        # 6. Track sustained elevated frames (for debounced alerts)
        if smoothed >= config.RISK_WARNING:
            self._sustained_elevated_frames += 1
        else:
            self._sustained_elevated_frames = max(0, self._sustained_elevated_frames - 2)

        trend = self._trend()

        return {
            "score":              smoothed,
            "raw_score":          round(raw_score, 1),
            "level":              display_level,
            "level_color":        LEVEL_COLORS.get(display_level, LEVEL_COLORS[LEVEL_SAFE]),
            "level_icon":         LEVEL_ICONS.get(display_level, LEVEL_ICONS[LEVEL_SAFE]),
            "recommended_action": RECOMMENDED_ACTIONS.get(display_level, RECOMMENDED_ACTIONS[LEVEL_SAFE]),
            "breakdown": {
                "density_score":    round(d_score, 1),
                "movement_score":   round(m_score, 1),
                "behavior_score":   round(b_score, 1),
                "congestion_score": round(cong_s, 1),
                "threat_score":     round(threat_s, 1),
                "stampede_synergy": round(stampede_synergy, 1),
            },
            "trend":                     trend,
            "history":                   list(self._risk_hist),
            "prediction_mode":           self.prediction_mode,
            "confidence":                round(ml_confidence, 1),
            "sustained_elevated_frames": self._sustained_elevated_frames,
            "person_count":              people_count,
        }

    def reset(self):
        """Reset temporal state for a new session."""
        self._risk_hist.clear()
        self._smoothed_score = 0.0
        self._sustained_elevated_frames = 0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _classify(self, score: float) -> str:
        """Classify score into standard 5-tier risk levels."""
        if score < config.RISK_SAFE:
            return LEVEL_SAFE
        elif score < config.RISK_CAUTION:
            return LEVEL_CAUTION
        elif score < config.RISK_WARNING:
            return LEVEL_WARNING
        elif score < config.RISK_HIGH:
            return LEVEL_HIGH
        else:
            return LEVEL_CRITICAL

    def _trend(self) -> str:
        """Compute rate of change over recent history."""
        if len(self._risk_hist) < 6:
            return "stable"
        recent   = sum(list(self._risk_hist)[-3:]) / 3
        previous = sum(list(self._risk_hist)[-6:-3]) / 3
        diff = recent - previous
        if diff > 3.0:
            return "increasing"
        elif diff < -3.0:
            return "decreasing"
        return "stable"
