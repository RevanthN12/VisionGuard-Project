class RiskEngine:
    def __init__(self, capacity=20):
        self.capacity = capacity

    def evaluate(self, people_count, weapons, violence_result, movement_result, decibels):
        """
        Combines multi-modal detections (visual + audio decibels) against risk matrix.
        Returns:
            result: dict with keys 'score', 'level', 'reason', 'action'
        """
        score = 0
        reasons = []
        
        # 1. Density component (up to 30)
        density_score = int((people_count / self.capacity) * 30)
        score += min(density_score, 30)
        if people_count > self.capacity:
            reasons.append("Crowd size exceeds zone capacity limit")
            
        # 2. Audio Decibels component
        if decibels >= 95.0:
            score += 25
            reasons.append("Extreme ambient decibel spikes (screams/gunshots)")
            
        # 3. Panic & Movement component
        panic_score = movement_result.get("panic_score", 0.0)
        if panic_score > 50.0:
            score += 30
            reasons.append(f"Chaotic crowd dispersion running pattern ({panic_score:.0f}%)")
            
        # 4. Violence component
        if violence_result.get("detected", False):
            score += 45
            reasons.append(f"Physical fight detected ({violence_result['probability']:.0f}% confidence)")
            
        # 5. Weapon component
        if len(weapons) > 0:
            score += 50
            best_weapon = weapons[0]
            reasons.append(f"Threat weapon detected: {best_weapon['label']} ({best_weapon['confidence']:.0f}% confidence)")
            
        # Cap score at 100
        score = min(score, 100)
        
        # Risk levels classification
        if score <= 30:
            level = "LOW"
            action = "Routine surveillance monitoring active."
        elif score <= 60:
            level = "MEDIUM"
            action = "Increase camera panning focus. Standby alerts."
        elif score <= 80:
            level = "HIGH"
            action = "Dispatch neighborhood security officers. Sound alarm logs."
        else:
            level = "CRITICAL"
            action = "Immediate law enforcement intervention and evacuation assessment required."
            
        # Formulate reason summary
        if len(reasons) == 0:
            reason = "No active security threats detected."
        else:
            reason = " + ".join(reasons)
            
        return {
            "score": score,
            "level": level,
            "reason": reason,
            "action": action
        }
