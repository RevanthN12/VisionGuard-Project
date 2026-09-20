"""
alert.py — Vision Guard Early Warning and Alert Module
Provides simple, high-visibility security alert generation and evidence logging.
"""

import time
import os
import threading
import config
import notifier
import database

# Global cooldown to prevent multiple cameras from sending external alerts simultaneously
_global_last_external_time = 0

# Minimum risk levels that trigger alerts
ALERTABLE_LEVELS = {"CAUTION", "WARNING", "HIGH RISK", "CRITICAL"}


class AlertManager:
    """Manages concise, deduplicated alert generation."""

    def __init__(self):
        self._last_alert_time: dict = {}   # level -> timestamp
        self._alert_log:       list = []   # in-memory log (last 100)
        self._sound_enabled         = True
        self._active_external_incident = False

    def check(self, risk_result: dict, behavior_result: dict,
              density_result: dict, camera_label="Camera 1") -> dict | None:
        """
        Evaluate current results and return a simple alert dict if warranted.
        """
        level = risk_result.get("level", "SAFE")
        
        if config.EXTERNAL_ALERTS_ENABLED and level not in config.EXTERNAL_ALERT_LEVELS:
            self._active_external_incident = False

        if level not in ALERTABLE_LEVELS:
            return None

        # Debounce alerts against single-frame detection noise:
        # Require sustained elevated evidence unless there is an immediate armed weapon threat
        sustained = risk_result.get("sustained_elevated_frames", 5)
        threat_score = risk_result.get("breakdown", {}).get("threat_score", 0.0)
        if sustained < 3 and threat_score < 80.0 and level in ("WARNING", "HIGH RISK"):
            return None

        now      = time.time()
        cooldown = config.ALERT_COOLDOWN.get(level, 8)
        last     = self._last_alert_time.get(level, 0)

        if (now - last) < cooldown:
            return None

        self._last_alert_time[level] = now

        evidence_path = risk_result.get("evidence_path", "")
        evidence_file = os.path.basename(evidence_path) if evidence_path else ""

        # Simplified alert message format
        score   = risk_result.get("score", 0)
        message = f"[{camera_label}] {level} ({score:.0f}%)"

        alert = {
            "timestamp":     time.strftime("%Y-%m-%dT%H:%M:%S"),
            "camera":        camera_label,
            "level":         level,
            "score":         score,
            "message":       message,
            "action":        risk_result.get("recommended_action", ""),
            "color":         risk_result.get("level_color", "#EF4444"),
            "evidence_path": evidence_path,
            "evidence_file": evidence_file
        }

        self._alert_log.append(alert)
        if len(self._alert_log) > 100:
            self._alert_log = self._alert_log[-100:]

        # Play alert sound for HIGH RISK and CRITICAL
        if self._sound_enabled and level in ("HIGH RISK", "CRITICAL"):
            self._play_sound(level)

        # External Alerts (Email & WhatsApp)
        if config.EXTERNAL_ALERTS_ENABLED and level in config.EXTERNAL_ALERT_LEVELS:
            if not self._active_external_incident:
                self._trigger_external_alerts(level, message, evidence_path, risk_result, density_result, camera_label)
                self._active_external_incident = True

        return alert

    def _play_sound(self, level: str):
        """Play simple alert sound in background thread."""
        def p():
            try:
                import winsound
                freq = 2500 if level == "CRITICAL" else 1800
                winsound.Beep(freq, 600)
            except Exception:
                pass
        threading.Thread(target=p, daemon=True).start()

    def _trigger_external_alerts(self, level, message, evidence_path, risk_result, density_result, camera_label="Camera 1"):
        """Spawns background threads for external notifications."""
        global _global_last_external_time
        now = time.time()
        if (now - _global_last_external_time) < 10:
            return
        _global_last_external_time = now

        subject = f"VISION GUARD ALERT [{camera_label}]: {level}"
        score   = risk_result.get("score", 0)
        people  = density_result.get("person_count", 0)

        import sys
        
        # Gather stats for the detailed report
        stats = database.get_session_stats(camera_label)
        recent = database.get_recent_incidents(2, camera_label)
        recent_str = ""
        for inc in recent:
            ts = inc.get("timestamp", "")[:16]  # YYYY-MM-DD HH:MM
            r = inc.get("risk_score", 0)
            p = inc.get("people_count", 0)
            recent_str += f"  - {ts}  Risk:{r:.0f}%  People:{p}\n"
            
        timestamp_now = time.strftime("%Y-%m-%d %H:%M:%S")

        try:
            body = (
                f"VISION GUARD ALERT [{camera_label}]: {level}\n\n"
                f"📍 LIVE STATUS\n"
                f"📷 Camera      : {camera_label}\n"
                f"📊 Risk Score  : {score:.0f}%\n"
                f"👥 People Count: {people}\n"
            )
            if evidence_path:
                body += f"📁 Evidence    : {evidence_path}\n"
                
            body += (
                f"⚡ Status      : 🔴 {level}: Risk score {score:.1f}%.  Immediate intervention required.\n\n\n"
                f"==============================\n"
                f"📋 SESSION REPORT\n"
                f"==============================\n"
                f"👥 Peak Crowd     : {stats.get('max_people', 0)} people\n"
                f"📊 Avg Crowd      : {stats.get('avg_people', 0):.0f} people\n"
                f"🔥 Max Risk Score : {stats.get('max_risk', 0):.0f}%\n"
                f"🚨 Total Incidents: {stats.get('total_incidents', 0)}\n"
                f"⚠️  Total Alerts   : {stats.get('total_alerts', 0)}\n"
                f"🕒 Timestamp      : {timestamp_now}\n"
                f"==============================\n"
                f"📌 Recent Incidents:\n"
            )
            if recent_str:
                body += recent_str
            else:
                body += "  - None\n"

            print(f"[AlertManager] PREPARING TO SEND EXTERNAL ALERTS for {level}. Thread starting...")
            sys.stdout.flush()

            def notify_bg():
                try:
                    print(f"[AlertManager-Thread] Inside notify_bg thread for {level}")
                    sys.stdout.flush()
                    att = [evidence_path] if (evidence_path and os.path.exists(evidence_path)) else None
                    
                    print(f"[AlertManager-Thread] Calling send_telegram_alert...")
                    sys.stdout.flush()
                    success = notifier.send_telegram_alert(body, image_path=evidence_path)
                    print(f"[AlertManager-Thread] Telegram dispatch status: {success}")
                    sys.stdout.flush()
                    
                except Exception as ex:
                    print(f"[AlertManager-Thread] CRITICAL ERROR IN THREAD: {ex}")
                    sys.stdout.flush()

            threading.Thread(target=notify_bg, daemon=True).start()
        except Exception as e:
            print(f"[AlertManager] Notification error: {e}")
            sys.stdout.flush()

    def get_recent_alerts(self, limit: int = 20) -> list:
        """Return the most recent alert dictionaries in reverse chronological order."""
        return list(reversed(self._alert_log[-limit:]))

    def clear(self):
        self._last_alert_time.clear()
        self._alert_log.clear()
        self._active_external_incident = False
