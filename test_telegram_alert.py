import sys
import time
sys.path.append(r"c:\Users\REVANTH NARENDRA\OneDrive\Desktop\projet1234\VisionGuard_Project (1)\VisionGuard_Project")
import notifier
import database

camera_label = "Test Camera"
level = "HIGH RISK"
score = 92.4
people = 115
evidence_path = "" # Skipping image for a quick text test

stats = database.get_session_stats(camera_label)
recent = database.get_recent_incidents(2, camera_label)
recent_str = ""
for inc in recent:
    ts = inc.get("timestamp", "")[:16]
    r = inc.get("risk_score", 0)
    p = inc.get("people_count", 0)
    recent_str += f"  - {ts}  Risk:{r:.0f}%  People:{p}\n"

timestamp_now = time.strftime("%Y-%m-%d %H:%M:%S")

body = (
    f"🚨 THIS IS A TEST ALERT 🚨\n\n"
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

print("Sending Telegram alert...")
success = notifier.send_telegram_alert(body)
print(f"Success: {success}")
