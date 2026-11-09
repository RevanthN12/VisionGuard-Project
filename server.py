import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

import time
import math
import threading
import cv2
import numpy as np
cv2.setNumThreads(1)
from collections import deque
from flask import Flask, jsonify, request, Response, send_from_directory, session, redirect
from werkzeug.security import check_password_hash
from flask_cors import CORS

import config
import database
import detection
import video_processor
import crowd_count
import density
import movement
import behavior_analysis
import risk_predictor
import evidence_recorder
import violence_detection
import weapon_detection
import noise_monitor
import alert
import face_recognition_system

try:
    from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
    PROMETHEUS_REQUESTS = Counter('visionguard_requests_total', 'Total HTTP Requests', ['method', 'endpoint'])
    PROMETHEUS_PERSON_COUNT = Gauge('visionguard_people_detected_total', 'Real-time person count detected by YOLO', ['camera'])
    PROMETHEUS_RISK_SCORE = Gauge('visionguard_risk_score', 'Real-time stampede risk score percentage', ['camera'])
except ImportError:
    PROMETHEUS_AVAILABLE = False

app = Flask(__name__, static_folder='frontend', static_url_path='/')
app.secret_key = 'super_secret_key_for_vision_guard'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 1000 * 1024 * 1024  # 1 GB max upload
CORS(app, supports_credentials=True)

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

@app.before_request
def require_login():
    # Only protect API routes
    unprotected = ('/api/login', '/api/logout', '/api/me', '/api/upload_video', '/api/samples', '/api/auto-login')
    if request.path.startswith('/api/') and request.path not in unprotected:
        if 'user_id' not in session:
            # Auto-assign guest session for open demo access
            user = database.get_user('admin')
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
            else:
                return jsonify({"success": False, "error": "Unauthorized"}), 401
        
        # Check admin-only routes (only destructive DB wipe requires admin)
        admin_routes = ['/api/settings/clear_db']
        if request.path in admin_routes and session.get('role') != 'admin':
            return jsonify({"success": False, "error": "Admin privileges required"}), 403

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"success": False, "error": "File size too large. Maximum allowed size is 1 GB."}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"success": False, "error": "Internal server error during video processing."}), 500

@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/api/'):
        return jsonify({"success": False, "error": f"API route '{request.path}' not found."}), 404
    return send_from_directory('frontend', 'home.html'), 404

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    user = database.get_user(username)
    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify({"success": True, "role": user['role']})
    return jsonify({"success": False, "error": "Invalid credentials"}), 401

@app.route('/api/auto-login', methods=['POST'])
def auto_login():
    """Auto-login for development/demo purposes using default admin account."""
    user = database.get_user('admin')
    if user:
        session['user_id'] = user['id']
        session['username'] = user['username']
        session['role'] = user['role']
        return jsonify({"success": True, "role": user['role']})
    return jsonify({"success": False, "error": "Admin account not found"}), 400

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route('/api/me', methods=['GET'])
def current_user():
    if 'user_id' in session:
        return jsonify({"success": True, "username": session['username'], "role": session['role']})
    return jsonify({"success": False, "error": "Not logged in"}), 401


# Global State
def create_camera_state():
    return {
        "running": False,
        "vp": None,
        "shared_from": None,
        "raw_frame": None,
        "frame_count": 0,
        "current_frame": None,
        "stats": {
            "person_count": 0,
            "density_score": 0,
            "density_level": "SAFE",
            "movement_speed": 0,
            "movement_level": "SAFE",
            "risk_score": 0,
            "risk_level": "SAFE",
            "risk_trend": "-",
            "recommended_action": "-",
            "violence_detected": False,
            "weapon_detected": False,
            "noise_db": 48.0,
            "alerts": []
        },
        "history": {
            "time": deque(maxlen=60),
            "count": deque(maxlen=60),
            "density": deque(maxlen=60),
            "risk": deque(maxlen=60)
        },
        "simulations": {
            "panic": False,
            "violence": False,
            "weapon": False,
            "scream": False,
            "tripwire": False,
            "loitering": False,
            "abandoned": False,
            "suspect": False,
            "fire": False,
            "fight": False
        },
        "loiter_memory": {},
        "abandoned_memory": {},
        "source_label": "Webcam"
    }

state = {
    "camera1": create_camera_state(),
    "camera2": create_camera_state()
}

cam_locks = {
    "camera1": threading.Lock(),
    "camera2": threading.Lock()
}

# Initialize modules once
print("Loading database...")
database.init_db()
print("* Database loaded")

print("Loading detection model...")
detection.load_model()
print("* Detection model loaded")

def create_analyzers():
    return {
        "counter": crowd_count.CrowdCounter(),
        "density_an": density.DensityAnalyzer(),
        "movement_an": movement.MovementAnalyzer(),
        "behavior_an": behavior_analysis.BehaviorAnalyzer(),
        "risk_pred": risk_predictor.RiskPredictor(),
        "recorder": evidence_recorder.EvidenceRecorder(),
        "violence_det": violence_detection.ViolenceDetector(),
        "weapon_det": weapon_detection.WeaponDetector(),
        "noise_mon": noise_monitor.NoiseMonitor(),
        "alerter": alert.AlertManager(),
        "face_rec": face_recognition_system.SuspectFaceRecognizer()
    }

analyzers = {
    "camera1": create_analyzers(),
    "camera2": create_analyzers()
}

print("Initialization complete. Starting Flask...")

def _draw_hud(frame, risk_r, count, density_r, movement_r, db=0):
    """Draw HUD overlay on top-left of frame."""
    cv2.rectangle(frame, (0, 0), (290, 136), (10, 12, 18), -1)
    level_bgr = {
        "SAFE":      (80, 220, 34),
        "CAUTION":   (8, 179, 234),
        "WARNING":   (22, 115, 249),
        "HIGH RISK": (34, 68, 239),
        "CRITICAL":  (125, 60, 124),
    }.get(risk_r.get("level", "SAFE"), (255, 255, 255))
    lines = [
        ("VISION GUARD AI",                                            (200, 200, 255)),
        (f"People : {count}",                                          (150, 255, 150)),
        (f"Density: {density_r.get('density_score',0):.0f}%  [{density_r.get('level','?')}]",
                                                                       (200, 220, 255)),
        (f"Motion : {movement_r.get('speed',0):.1f}px/f  [{movement_r.get('level','?')}]",
                                                                       (200, 220, 255)),
        (f"RISK   : {risk_r.get('level','?')}  ({risk_r.get('score',0):.0f}%)",
                                                                       level_bgr),
        (f"AUDIO  : {db:.1f} dB",                                       (255, 180, 180)),
    ]
    for i, (txt, col) in enumerate(lines):
        cv2.putText(frame, txt, (8, 22 + i * 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.46, col, 1)

def video_processing_loop(camera_id):
    last_db_log = 0
    cam_state = state[camera_id]
    cam_analyzers = analyzers[camera_id]
    
    counter = cam_analyzers["counter"]
    density_an = cam_analyzers["density_an"]
    movement_an = cam_analyzers["movement_an"]
    behavior_an = cam_analyzers["behavior_an"]
    risk_pred = cam_analyzers["risk_pred"]
    recorder = cam_analyzers["recorder"]
    violence_det = cam_analyzers["violence_det"]
    weapon_det = cam_analyzers["weapon_det"]
    noise_mon = cam_analyzers["noise_mon"]
    alerter = cam_analyzers["alerter"]

    camera_label = "Camera 1" if camera_id == "camera1" else "Camera 2"

    while True:
        try:
            ok = False
            frame = None
            with cam_locks[camera_id]:
                if cam_state["running"]:
                    shared_src = cam_state.get("shared_from")
                    if shared_src:
                        other_st = state.get(shared_src, {})
                        if other_st.get("running") and other_st.get("raw_frame") is not None:
                            ok = True
                            frame = other_st["raw_frame"].copy()
                    elif cam_state["vp"] is not None:
                        ok, frame = cam_state["vp"].read_frame()
                        if ok and frame is not None:
                            cam_state["raw_frame"] = frame.copy()
            
            if not ok or frame is None:
                time.sleep(0.03)
                continue
            
            cam_state["frame_count"] = cam_state.get("frame_count", 0) + 1
            if cam_state["frame_count"] % 30 == 0:
                print(f"[Loop {camera_id}] Frame #{cam_state['frame_count']} (FPS: {cam_state.get('processing_fps', 0):.1f})", flush=True)

            # Dynamic loop execution FPS tracking for 1.0x normal-speed video recording
            loop_now = time.time()
            if cam_state.get("last_loop_t", 0) > 0:
                dt_loop = loop_now - cam_state["last_loop_t"]
                if dt_loop > 0:
                    inst_fps = 1.0 / dt_loop
                    cam_state["processing_fps"] = 0.85 * cam_state.get("processing_fps", 10.0) + 0.15 * inst_fps
            cam_state["last_loop_t"] = loop_now

            # ── 1. Object Detection (People + Weapons) ───────────
            run_weapons = True
            det = detection.detect_persons(frame, draw=True, detect_weapons=run_weapons)
            ann = det["annotated_frame"]
            
            # Check for weapons immediately
            weapon_detected = any(d.get("is_weapon", False) for d in det["detections"])
            cnt = det["person_count"]

            # ── Fire Detection ───────────────────────────────────
            fire_detected = False
            if cam_state["simulations"]["fire"]:
                ann, fire_detected = detection.detect_fire(ann)

            counter.update(cnt)
            dens = density_an.analyze(det["detections"], frame.shape[1], frame.shape[0])
            move = movement_an.analyze(frame)
            behv = behavior_an.analyze(dens, move)
            viol = violence_det.analyze(move, inject_simulation=cam_state["simulations"]["violence"])
            
            # Fast weapon handling without redundant duplicate neural network inference
            if cam_state["simulations"]["weapon"]:
                weap = weapon_det.detect(ann, inject_simulation=True)
            else:
                weapon_boxes = [d for d in det["detections"] if d.get("is_weapon")]
                weap = {
                    "available": True,
                    "detected": weapon_detected,
                    "weapons": weapon_boxes,
                    "score": max([d.get("confidence", 0) for d in weapon_boxes], default=0.0)
                }
            risk = risk_pred.predict(dens, move, behv, viol, weap, people_count=cnt)
            
            # Audio processing
            db = noise_mon.get_decibels(inject_scream=cam_state["simulations"]["scream"])
            if db > 95.0:
                risk["score"] = max(risk.get("score", 0), 90.0)
                risk["level"] = "CRITICAL"
                risk["level_color"] = "#7D3C7C" # Purple for critical
                risk["recommended_action"] = "LOUD NOISE DETECTED. Possible gunshot/scream."

            # Simulation override (Panic)
            if cam_state["simulations"]["panic"]:
                risk["score"] = max(risk.get("score", 0), 75.0)
                risk["level"] = "HIGH RISK"
                risk["level_color"] = "#EF4444"
                risk["recommended_action"] = "Activate emergency response. Control entry points immediately."

            # ── Apply Threat Overrides ───────────────────────────
            if weapon_detected:
                risk["score"] = 100.0
                risk["level"] = "CRITICAL"
                risk["level_color"] = "#FF0000"
                risk["recommended_action"] = "ARMED SUSPECT DETECTED! DISPATCH ARMED RESPONSE UNIT."
                
            if fire_detected:
                risk["score"] = 100.0
                risk["level"] = "CRITICAL"
                risk["level_color"] = "#FF4500"
                risk["recommended_action"] = "FIRE DETECTED! INITIATE EVACUATION AND CALL FIRE DEPARTMENT."

            # Suspect Face Recognition
            if cam_state["simulations"]["suspect"]:
                ann, found, name = cam_analyzers["face_rec"].detect_suspects(ann, det.get("detections", []))
                if found:
                    risk["score"] = 100.0
                    risk["level"] = "CRITICAL"
                    risk["level_color"] = "#FF0055"
                    risk["recommended_action"] = f"WANTED SUSPECT ({name}) DETECTED! DISPATCH SECURITY IMMEDIATELY."

            if cam_state["simulations"]["fight"]:
                if cnt >= 2:
                    # Heuristic: Check if any two people are very close to each other
                    people = [d for d in det["detections"] if d.get("class_id") == 0]
                    fight_found = False
                    for i in range(len(people)):
                        for j in range(i+1, len(people)):
                            cx1, cy1 = people[i]["centroid"]
                            cx2, cy2 = people[j]["centroid"]
                            if math.hypot(cx1 - cx2, cy1 - cy2) < 80:  # Close proximity
                                fight_found = True
                                break
                        if fight_found: break
                    
                    if fight_found:
                        risk["score"] = 90.0
                        risk["level"] = "CRITICAL"
                        risk["level_color"] = "#8B0000"
                        risk["recommended_action"] = "VIOLENCE / FIGHT DETECTED! DISPATCH SECURITY TO SEPARATE INDIVIDUALS."
                        cv2.putText(ann, "FIGHT DETECTED", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)

            # Virtual Tripwire & Intrusion Detection
            if cam_state["simulations"]["tripwire"]:
                h, w = frame.shape[:2]
                tripwire_y = int(h * 0.5)  # Middle of the screen
                
                # Draw the restricted zone (bottom half)
                overlay = ann.copy()
                cv2.rectangle(overlay, (0, tripwire_y), (w, h), (0, 0, 150), -1)
                cv2.addWeighted(overlay, 0.25, ann, 0.75, 0, ann)
                
                # Draw the glowing neon tripwire
                cv2.line(ann, (0, tripwire_y), (w, tripwire_y), (0, 240, 255), 2)
                cv2.putText(ann, "RESTRICTED ZONE - DO NOT CROSS", (10, tripwire_y + 25), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                
                # Check for intrusions
                intrusion_detected = False
                for person in det["detections"]:
                    cx, cy = person["centroid"]
                    if cy > tripwire_y:
                        intrusion_detected = True
                        # Highlight the intruder with a thick red box
                        x1, y1, x2, y2 = person["box"]
                        cv2.rectangle(ann, (x1, y1), (x2, y2), (0, 0, 255), 4)
                        cv2.putText(ann, "INTRUDER", (x1, y1 - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                
                if intrusion_detected:
                    risk["score"] = 100.0
                    risk["level"] = "CRITICAL"
                    risk["level_color"] = "#D900FF"
                    risk["recommended_action"] = "INTRUSION DETECTED IN RESTRICTED ZONE. DISPATCH SECURITY."

            # Stationary & Loitering Monitoring (Track dwell time without hardcoded risk overrides)
            current_ids = set()
            now = time.time()
            for person in det["detections"]:
                tid = person.get("track_id")
                if tid is None:
                    continue
                current_ids.add(tid)
                cx, cy = person["centroid"]
                
                if tid not in cam_state["loiter_memory"]:
                    cam_state["loiter_memory"][tid] = {"start_time": now, "start_pos": (cx, cy)}
                else:
                    mem = cam_state["loiter_memory"][tid]
                    sx, sy = mem["start_pos"]
                    dist = math.hypot(cx - sx, cy - sy)
                    
                    if dist > 60:  # Moved significantly, reset timer
                        cam_state["loiter_memory"][tid] = {"start_time": now, "start_pos": (cx, cy)}
                    else:
                        elapsed = now - mem["start_time"]
                        # Informative visual indicator if stationary for more than 8 seconds
                        if elapsed >= 8.0:
                            x1, y1, x2, y2 = person["box"]
                            cv2.rectangle(ann, (x1, y1), (x2, y2), (255, 165, 0), 2)
                            cv2.putText(ann, f"STATIONARY {int(elapsed)}s", (x1, y1 - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
            
            # Clean up old tracking memory
            for tid in list(cam_state["loiter_memory"].keys()):
                if tid not in current_ids:
                    del cam_state["loiter_memory"][tid]
                        
            # Abandoned Object Detection
            if cam_state["simulations"]["abandoned"]:
                current_bag_ids = set()
                now = time.time()
                for obj in det["detections"]:
                    # Check if the object is a bag/suitcase (YOLO classes 24, 26, 28)
                    if obj.get("class_id") not in [24, 26, 28]:
                        continue
                        
                    tid = obj.get("track_id")
                    if tid is None:
                        continue
                        
                    current_bag_ids.add(tid)
                    cx, cy = obj["centroid"]
                    
                    if tid not in cam_state["abandoned_memory"]:
                        cam_state["abandoned_memory"][tid] = {"start_time": now, "start_pos": (cx, cy)}
                    else:
                        mem = cam_state["abandoned_memory"][tid]
                        sx, sy = mem["start_pos"]
                        dist = math.hypot(cx - sx, cy - sy)
                        
                        if dist > 40:  # Bag was moved
                            cam_state["abandoned_memory"][tid] = {"start_time": now, "start_pos": (cx, cy)}
                        else:
                            elapsed = now - mem["start_time"]
                            if elapsed > 10.0:  # Bag stationary for > 10 seconds
                                risk["score"] = 100.0
                                risk["level"] = "CRITICAL"
                                risk["level_color"] = "#FF003C"
                                risk["recommended_action"] = "ABANDONED OBJECT DETECTED. DISPATCH BOMB SQUAD / SECURITY."
                                
                                x1, y1, x2, y2 = obj["box"]
                                cv2.rectangle(ann, (x1, y1), (x2, y2), (0, 0, 255), 4)
                                cv2.putText(ann, f"SUSPICIOUS OBJECT ({int(elapsed)}s)", (x1, y1 - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
                # Clean up missing bags
                for tid in list(cam_state["abandoned_memory"].keys()):
                    if tid not in current_bag_ids:
                        del cam_state["abandoned_memory"][tid]

            # Evidence recording logic
            ev_img = None
            current_ev_path = None
            
            risk_hierarchy = {"SAFE": 0, "CAUTION": 1, "WARNING": 2, "HIGH RISK": 3, "HIGH_RISK": 3, "CRITICAL": 4}
            current_val = risk_hierarchy.get(risk.get("level", "SAFE"), 0)
            min_val = risk_hierarchy.get(config.EVIDENCE_MIN_RISK, 3)
            is_high_risk = current_val >= min_val

            if is_high_risk:
                ev_img = recorder.save_snapshot(ann, risk, dens, move, cnt, camera_label)
                if not getattr(recorder, "_recording", False):
                    actual_loop_fps = cam_state.get("processing_fps", 10.0)
                    recorder.start_clip(ann, risk["level"], camera_label, fps=actual_loop_fps, risk_score=risk.get("score", 0), person_count=cnt)
            
            if getattr(recorder, "_recording", False):
                recorder.write_frame(ann, is_high_risk)
                current_ev_path = getattr(recorder, "_current_clip", None) or ev_img
                risk["evidence_path"] = ev_img or current_ev_path or ""
            else:
                current_ev_path = ev_img or getattr(recorder, "_current_clip", None)
                risk["evidence_path"] = current_ev_path or ""

            # Ensure the current frame is in the DB before alerts are processed
            # so that Telegram statistics queries include the current peak/averages
            now = time.time()
            if (now - last_db_log >= 10) or is_high_risk or current_val >= 2: # >= WARNING
                last_db_log = now
                database.log_frame(cam_state["source_label"], cnt, dens, move, risk)

            alrt = alerter.check(risk, behv, dens, camera_label)

            # Debounced incident logging (once every 12 seconds per camera, or on new alert)
            last_inc_log = cam_state.get("last_incident_log", 0)
            if alrt or (is_high_risk and (now - last_inc_log >= 12.0)):
                cam_state["last_incident_log"] = now
                database.log_incident(
                    cam_state["source_label"], cnt, dens, move, behv, viol, weap, risk,
                    alrt["message"] if alrt else f"[{camera_label}] {risk['level']} ({risk['score']:.0f}%)",
                    current_ev_path or "")
            if alrt:
                database.log_alert(alrt)

            _draw_hud(ann, risk, cnt, dens, move, db)

            # Update global state with all dynamic real-time decision features
            threat_label = "WEAPON DETECTED" if weap.get("detected") else ("VIOLENCE DETECTED" if viol.get("detected") else "CLEAR")
            cam_state["stats"] = {
                "person_count": cnt,
                "density_score": dens["density_score"],
                "density_level": dens["level"],
                "movement_speed": move["speed"],
                "movement_level": move["level"],
                "congestion_score": round(risk.get("breakdown", {}).get("congestion_score", 0), 1),
                "congestion_frames": behv.get("congestion_frames", 0),
                "behavior_status": behv["status"],
                "violence_detected": viol["detected"],
                "weapon_detected": weap.get("detected", False),
                "threat_status": threat_label,
                "risk_score": risk["score"],
                "risk_level": risk["level"],
                "risk_trend": risk.get("trend", "-"),
                "recommended_action": risk.get("recommended_action", "-"),
                "noise_db": db,
                "evidence_path": current_ev_path or "",
                "evidence_file": os.path.basename(current_ev_path) if current_ev_path else "",
                "breakdown": risk.get("breakdown", {}),
                "alerts": ([f"[{camera_label}] {risk['level']} ({risk['score']:.0f}%) - {risk.get('recommended_action', 'ELEVATED RISK')}"] if is_high_risk else ([alrt["message"]] if alrt else []))
            }

            # Update history for charts
            ts = time.strftime("%H:%M:%S")
            cam_state["history"]["time"].append(ts)
            cam_state["history"]["count"].append(cnt)
            cam_state["history"]["density"].append(dens["density_score"])
            cam_state["history"]["risk"].append(risk["score"])

            # Store latest frame for MJPEG stream with high-speed JPEG compression
            ret, buffer = cv2.imencode('.jpg', ann, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ret:
                cam_state["current_frame"] = buffer.tobytes()

        except Exception as e:
            import traceback
            print(f"[Loop Exception {camera_id}] Error in video processing loop: {e}")
            traceback.print_exc()
            time.sleep(1.0)

# Start background threads
threading.Thread(target=video_processing_loop, args=("camera1",), daemon=True).start()
threading.Thread(target=video_processing_loop, args=("camera2",), daemon=True).start()

# Server starts with cameras stopped by default. Cameras will open when user clicks Start in dashboard.
print("[Server] Ready. Surveillance streams waiting for user start command...")

# --- ROUTES ---
@app.route('/')
def home():
    return send_from_directory('frontend', 'home.html')

@app.route('/login_page')
def login_page():
    if 'user_id' in session:
        return redirect('/dashboard')
    return send_from_directory('frontend', 'login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login_page')
    return send_from_directory('frontend', 'index.html')

@app.route('/api/stats', methods=['GET'])
def get_stats():
    return jsonify({
        "camera1": {
            "running": state["camera1"]["running"],
            "stats": state["camera1"]["stats"]
        },
        "camera2": {
            "running": state["camera2"]["running"],
            "stats": state["camera2"]["stats"]
        }
    })

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get recent alerts (HIGH RISK, CRITICAL, WARNING, etc.)"""
    n = request.args.get('n', 20, type=int)
    return jsonify({
        "camera1": {
            "alerts": analyzers["camera1"]["alerter"].get_recent_alerts(n)
        },
        "camera2": {
            "alerts": analyzers["camera2"]["alerter"].get_recent_alerts(n)
        }
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify({
        "camera1": {
            "time": list(state["camera1"]["history"]["time"]),
            "count": list(state["camera1"]["history"]["count"]),
            "density": list(state["camera1"]["history"]["density"]),
            "risk": list(state["camera1"]["history"]["risk"])
        },
        "camera2": {
            "time": list(state["camera2"]["history"]["time"]),
            "count": list(state["camera2"]["history"]["count"]),
            "density": list(state["camera2"]["history"]["density"]),
            "risk": list(state["camera2"]["history"]["risk"])
        }
    })

@app.route('/api/detect_cameras', methods=['GET'])
def detect_cameras():
    cams = video_processor.detect_available_webcams()
    
    # If a webcam is already actively running, ensure it remains in the detected list
    running_indices = set()
    for cid in ("camera1", "camera2"):
        st = state[cid]
        if st["running"] and st["vp"] and st["vp"].source_type == video_processor.VideoProcessor.SOURCE_WEBCAM:
            try:
                running_indices.add(int(st["vp"].source_path))
            except Exception:
                pass
                
    detected_indices = {c["index"] for c in cams}
    for r_idx in running_indices:
        if r_idx not in detected_indices:
            cams.insert(0, {
                "index": r_idx,
                "label": f"Webcam #{r_idx} (Active In-Use)",
                "name": f"Webcam #{r_idx}",
                "resolution": "640x480"
            })
            
    return jsonify({"success": True, "cameras": cams})

@app.route('/api/start', methods=['POST'])
def start_monitoring():
    data = request.json or {}
    src_type = data.get("src_type", "Webcam")
    param = data.get("param", 0)
    camera_id = data.get("camera_id", "both")

    # Clear frame history for new session so analytics only show current session
    database.clear_session_telemetry()

    def start_cam(cid, p):
        with cam_locks[cid]:
            cam_state = state[cid]
            cam_analyzers = analyzers[cid]
            cam_state["running"] = False
            cam_state["shared_from"] = None
            time.sleep(0.05)
            if cam_state["vp"]:
                cam_state["vp"].release()
                cam_state["vp"] = None
            vp = video_processor.VideoProcessor()
            ok = False

            if src_type == "Webcam":
                try:
                    cam_idx = int(p)
                except (ValueError, TypeError):
                    cam_idx = 0

                other_cid = "camera2" if cid == "camera1" else "camera1"
                other_state = state[other_cid]

                # Check if this webcam is already in use by the other running camera
                is_same_as_other = (
                    other_state["running"] and 
                    other_state.get("vp") and 
                    other_state["vp"].source_type == video_processor.VideoProcessor.SOURCE_WEBCAM and
                    str(other_state["vp"].source_path) == str(cam_idx)
                )

                if is_same_as_other:
                    # Check if another distinct physical webcam is available
                    avail = video_processor.detect_available_webcams()
                    other_avail = [c["index"] for c in avail if c["index"] != cam_idx]
                    if other_avail:
                        cam_idx = other_avail[0]
                        ok = vp.open_webcam(cam_idx)
                        cam_state["source_label"] = f"Webcam #{cam_idx}"
                    else:
                        # Only 1 physical camera connected: share the live webcam frame!
                        print(f"[Server] Single webcam detected. Sharing live feed from {other_cid} to {cid}.")
                        cam_state["shared_from"] = other_cid
                        cam_state["source_label"] = f"Webcam #{cam_idx} (Live Shared)"
                        ok = True
                else:
                    ok = vp.open_webcam(cam_idx)
                    cam_state["source_label"] = f"Webcam #{cam_idx}"

                    # If requested index failed and wasn't 0, try default 0
                    if not ok and cam_idx != 0:
                        print(f"[Server] Webcam #{cam_idx} unavailable. Retrying with Webcam #0...")
                        if other_state["running"] and str(getattr(other_state.get("vp"), "source_path", "")) == "0":
                            cam_state["shared_from"] = other_cid
                            cam_state["source_label"] = "Webcam #0 (Live Shared)"
                            ok = True
                        else:
                            ok = vp.open_webcam(0)
                            if ok:
                                cam_state["source_label"] = "Webcam #0"

            elif src_type == "Sample":
                sample_name = str(p) if p else "crowd_sample_1.mp4"
                ok = vp.open_sample(sample_name)
                cam_state["source_label"] = f"Sample: {sample_name}"
            elif src_type == "RTSP":
                ok = vp.open_rtsp(str(p))
                cam_state["source_label"] = f"Stream: {p}"

            if not ok and src_type != "Webcam":
                # Fallback to sample video ONLY if the source was already a file/sample/RTSP
                samples = vp.get_sample_videos()
                if samples:
                    fallback_sample = samples[1] if (len(samples) > 1 and cid == "camera2") else samples[0]
                    print(f"[Server] Primary source '{p}' unavailable for {cid}. Falling back to sample video '{fallback_sample}'.")
                    ok = vp.open_sample(fallback_sample)
                    cam_state["source_label"] = f"Sample (Dual Cam): {fallback_sample}"
                if not ok:
                    ok = vp.open_synthetic()
                    cam_state["source_label"] = "Synthetic Stream"

            if ok:
                if cam_state.get("shared_from") is None:
                    cam_state["vp"] = vp
                cam_state["running"] = True
                cam_analyzers["counter"].reset()
                cam_analyzers["behavior_an"].reset()
                cam_analyzers["risk_pred"].reset()
                cam_analyzers["movement_an"].reset()
                cam_analyzers["alerter"].clear()
                for k in cam_state["history"]:
                    cam_state["history"][k].clear()
                print(f"[Server] start_cam {cid}: ok={ok}, source={cam_state['source_label']}, running={cam_state['running']}", flush=True)
            else:
                print(f"[Server] start_cam {cid} FAILED: ok=False", flush=True)
            return ok

    if camera_id == "both":
        if src_type == "Webcam":
            cams = video_processor.detect_available_webcams()
            if len(cams) >= 2:
                # 2 physical USB cameras plugged in! Assign 1st to Cam 1, 2nd to Cam 2
                p1 = cams[0]["index"]
                p2 = cams[1]["index"]
                print(f"[Server] Dual USB cameras detected: Cam 1 -> Index #{p1}, Cam 2 -> Index #{p2}")
                ok1 = start_cam("camera1", p1)
                ok2 = start_cam("camera2", p2)
            else:
                p1 = cams[0]["index"] if cams else 0
                ok1 = start_cam("camera1", p1)
                ok2 = False
                try:
                    target_p2 = int(param)
                except (ValueError, TypeError):
                    target_p2 = 0
                if target_p2 != p1:
                    print(f"[Server] Trying user-selected webcam #{target_p2} for Camera 2...")
                    ok2 = start_cam("camera2", target_p2)
                if not ok2 and ok1:
                    with cam_locks["camera2"]:
                        state["camera2"]["running"] = False
                        if state["camera2"]["vp"]:
                            state["camera2"]["vp"].release()
                            state["camera2"]["vp"] = None
                        state["camera2"]["shared_from"] = "camera1"
                        state["camera2"]["source_label"] = f"Webcam #{p1} (Live Shared)"
                        state["camera2"]["running"] = True
                        for k in state["camera2"]["history"]:
                            state["camera2"]["history"][k].clear()
                    ok2 = True
        elif src_type == "Sample":
            vp_test = video_processor.VideoProcessor()
            all_samples = vp_test.get_sample_videos()
            p1 = param
            p2 = param
            if len(all_samples) > 1:
                other_samples = [s for s in all_samples if s != param]
                if other_samples:
                    p2 = other_samples[0]
            ok1 = start_cam("camera1", p1)
            ok2 = start_cam("camera2", p2)
        else:
            ok1 = start_cam("camera1", param)
            ok2 = start_cam("camera2", param)

        if ok1 or ok2:
            return jsonify({"success": True, "camera1": ok1, "camera2": ok2})
        else:
            return jsonify({"success": False, "error": "Failed to open video sources."})
    else:
        ok = start_cam(camera_id, param)
        if ok:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": f"Failed to open video source for {camera_id}."})

@app.route('/api/stop', methods=['POST'])
def stop_monitoring():
    data = request.json or {}
    camera_id = data.get("camera_id", "both")
    
    def stop_cam(cid):
        with cam_locks[cid]:
            cam_state = state[cid]
            cam_state["running"] = False
            cam_state["shared_from"] = None
            cam_state["raw_frame"] = None
            time.sleep(0.05)
            if analyzers[cid]["recorder"]._recording:
                analyzers[cid]["recorder"].stop_clip()
            if cam_state["vp"]:
                cam_state["vp"].release()
                cam_state["vp"] = None
            cam_state["current_frame"] = None
            
            # If the other camera was sharing from cid, stop it too
            other_cid = "camera2" if cid == "camera1" else "camera1"
            if state[other_cid].get("shared_from") == cid:
                state[other_cid]["running"] = False
                state[other_cid]["shared_from"] = None
                state[other_cid]["raw_frame"] = None
                state[other_cid]["current_frame"] = None

    if camera_id == "both":
        stop_cam("camera1")
        stop_cam("camera2")
    else:
        stop_cam(camera_id)
        
    return jsonify({"success": True})

@app.route('/api/simulate', methods=['POST'])
def toggle_simulation():
    data = request.json
    sim_type = data.get("type")
    active = data.get("active", False)
    # Apply simulation to both cameras for now
    if sim_type in state["camera1"]["simulations"]:
        state["camera1"]["simulations"][sim_type] = active
        state["camera2"]["simulations"][sim_type] = active
    return jsonify({"success": True})

@app.route('/api/test_telegram', methods=['POST', 'GET'])
def api_test_telegram():
    import notifier
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    camera_label = "Camera 1"
    level = "HIGH RISK"
    score = 75.0
    people = state["camera1"]["stats"].get("person_count", 1) or 1
    
    # Save live frame as evidence photo
    ev_path = None
    for cid in ("camera1", "camera2"):
        if state[cid].get("current_frame"):
            test_img_path = os.path.join(config.EVIDENCE_IMG_DIR, f"Camera_1_Evidence_{time.strftime('%Y%m%d_%H%M%S')}.jpg")
            with open(test_img_path, "wb") as f:
                f.write(state[cid]["current_frame"])
            ev_path = test_img_path
            break
            
    stats = database.get_session_stats(camera_label)
    peak_crowd = max(people, int(stats.get('max_people', 0)))
    avg_crowd = max(people, int(stats.get('avg_people', 0)))
    max_risk = max(score, float(stats.get('max_risk', 0)))
    total_incidents = max(1, int(stats.get('total_incidents', 0)))
    total_alerts = stats.get('total_alerts', 0)
    
    recent = database.get_recent_incidents(2, camera_label)
    recent_str = ""
    for inc in recent:
        ts = inc.get("timestamp", "")[:16]
        r = inc.get("risk_score", 0)
        p = inc.get("people_count", 0)
        recent_str += f"  - {ts}  Risk:{r:.0f}%  People:{p}\n"

    msg = (
        f"VISION GUARD ALERT [{camera_label}]: {level}\n\n"
        f"📍 LIVE STATUS\n"
        f"📷 Camera      : {camera_label}\n"
        f"📊 Risk Score  : {score:.0f}%\n"
        f"👥 People Count: {people}\n"
    )
    if ev_path:
        msg += f"📁 Evidence    : {ev_path}\n"
    msg += (
        f"⚡ Status      : 🔴 {level}: Risk score {score:.1f}%.  Immediate intervention required.\n\n\n"
        f"==============================\n"
        f"📋 SESSION REPORT\n"
        f"==============================\n"
        f"👥 Peak Crowd     : {peak_crowd} people\n"
        f"📊 Avg Crowd      : {avg_crowd} people\n"
        f"🔥 Max Risk Score : {max_risk:.0f}%\n"
        f"🚨 Total Incidents: {total_incidents}\n"
        f"⚠️  Total Alerts   : {total_alerts}\n"
        f"🕒 Timestamp      : {timestamp}\n"
        f"==============================\n"
        f"📌 Recent Incidents:\n"
    )
    if recent_str:
        msg += recent_str
    else:
        msg += f"  - {timestamp[:16]}  Risk:{score:.0f}%  People:{people}\n"

    success = notifier.send_telegram_alert(msg, image_path=ev_path)
    return jsonify({"success": success, "message": "Telegram alert dispatched successfully!" if success else "Failed to dispatch Telegram message."})

@app.route('/api/config/update', methods=['POST'])
def update_config():
    data = request.json
    key = data.get("key")
    val = data.get("value")
    
    if key == "yolo_conf":
        config.YOLO_CONF = float(val) / 100.0
    # Additional keys could be mapped here if needed.
    
    return jsonify({"success": True, "updated": key, "value": val})

@app.route('/video_feed/<camera_id>')
def video_feed(camera_id):
    def generate(cid):
        # Create lightweight placeholder frame for connection startup
        placeholder = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(placeholder, f"VisionGuard - {cid.upper()}", (140, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 240, 255), 2)
        cv2.putText(placeholder, "Connecting to camera feed...", (175, 260), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (160, 160, 160), 1)
        _, ph_buf = cv2.imencode('.jpg', placeholder)
        ph_bytes = ph_buf.tobytes()

        while True:
            frame_data = state[cid].get("current_frame")
            if state[cid].get("running", False) and frame_data:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n'
                       b'Content-Length: ' + str(len(frame_data)).encode() + b'\r\n'
                       b'\r\n' + frame_data + b'\r\n')
                time.sleep(0.033)
            else:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n'
                       b'Content-Length: ' + str(len(ph_bytes)).encode() + b'\r\n'
                       b'\r\n' + ph_bytes + b'\r\n')
                time.sleep(0.2)
                
        # Yield one last black/offline frame and close connection
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n'
               b'Content-Length: ' + str(len(ph_bytes)).encode() + b'\r\n'
               b'\r\n' + ph_bytes + b'\r\n'
               b'--frame--\r\n')

    return Response(generate(camera_id), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/samples', methods=['GET'])
def get_samples():
    vp = video_processor.VideoProcessor()
    return jsonify({"samples": vp.get_sample_videos()})

@app.route('/api/upload_video', methods=['POST'])
def upload_video():
    try:
        if 'video' not in request.files:
            return jsonify({"success": False, "error": "No video file received"}), 400
        
        file = request.files['video']
        if not file or file.filename == '':
            return jsonify({"success": False, "error": "No video file selected"}), 400

        raw_filename = file.filename
        from werkzeug.utils import secure_filename
        sec_filename = secure_filename(raw_filename)
        
        ext = os.path.splitext(raw_filename)[1].lower()
        if not ext:
            ext = os.path.splitext(sec_filename)[1].lower() or '.mp4'

        allowed_exts = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv'}
        if ext not in allowed_exts:
            return jsonify({"success": False, "error": f"Invalid format '{ext}'. Supported formats: .mp4, .avi, .mov, .mkv, .webm, .flv"}), 400

        if not sec_filename or sec_filename.startswith('.'):
            base_name = os.path.splitext(raw_filename)[0].replace(' ', '_')
            sec_filename = f"{base_name}_{int(time.time())}{ext}"
        if not sec_filename.endswith(ext):
            sec_filename += ext

        target_dir = config.SAMPLE_VIDEOS_DIR
        os.makedirs(target_dir, exist_ok=True)
        save_path = os.path.join(target_dir, sec_filename)

        file.seek(0)
        file.save(save_path)

        try:
            os.makedirs("uploads", exist_ok=True)
            import shutil
            shutil.copy(save_path, os.path.join("uploads", sec_filename))
        except Exception as e:
            print(f"[Server] Upload backup notice: {e}")

        vp = video_processor.VideoProcessor()
        samples = vp.get_sample_videos()

        print(f"[Server] Uploaded crowd video successfully saved: {save_path} ({os.path.getsize(save_path)} bytes)")
        return jsonify({
            "success": True,
            "filename": sec_filename,
            "samples": samples,
            "message": f"Video '{sec_filename}' uploaded successfully!"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Server error processing upload: {str(e)}"}), 500

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    cam = request.args.get("camera")
    return jsonify({
        "stats": database.get_session_stats(video_source=cam),
        "camera1_stats": database.get_session_stats("Camera 1"),
        "camera2_stats": database.get_session_stats("Camera 2"),
        "history": database.get_recent_history(300, video_source=cam),
        "incidents": database.get_recent_incidents(20, video_source=cam)
    })

@app.route('/api/evidence', methods=['GET'])
def get_evidence():
    return jsonify({"files": analyzers["camera1"]["recorder"].list_evidence(40)})

@app.route('/api/evidence/img/<filename>', methods=['GET'])
def serve_evidence_img(filename):
    return send_from_directory(config.EVIDENCE_IMG_DIR, filename)

@app.route('/api/evidence/vid/<filename>', methods=['GET'])
def serve_evidence_vid(filename):
    return send_from_directory(config.EVIDENCE_VID_DIR, filename)

@app.route('/api/reports/generate_csv', methods=['POST'])
def generate_report_csv():
    import report_generator
    data = request.json or {}
    cam = data.get("camera")
    filepath = report_generator.generate_csv(video_source=cam)
    return jsonify({"success": True, "filename": os.path.basename(filepath)})

@app.route('/api/reports/generate_pdf', methods=['POST'])
def generate_report_pdf():
    import report_generator
    data = request.json or {}
    cam = data.get("camera")
    filepath = report_generator.generate_pdf(video_source=cam)
    if filepath:
        return jsonify({"success": True, "filename": os.path.basename(filepath)})
    return jsonify({"success": False, "error": "PDF generation failed."})

@app.route('/api/reports/download/<filename>', methods=['GET'])
def download_report(filename):
    return send_from_directory(config.REPORTS_DIR, filename, as_attachment=True)

@app.route('/api/chat', methods=['POST'])
def chat():
    import ai_assistant
    data = request.json
    query = data.get("query", "")
    
    # Mock Streamlit session state for the chatbot using camera1
    mock_state = {
        "running": state["camera1"]["running"],
        "count_hist": state["camera1"]["history"]["count"],
        "density_hist": state["camera1"]["history"]["density"],
        "risk_hist": state["camera1"]["history"]["risk"],
    }
    
    # Let chatbot read from mock state
    response = ai_assistant.generate_response(query, mock_state)
    return jsonify({"response": response})

@app.route('/api/settings/clear_db', methods=['POST'])
def clear_db():
    # Clear physical db and files
    success = database.clear_database()
    
    # Clear in-memory history
    for cid in ["camera1", "camera2"]:
        for k in state[cid]["history"]:
            state[cid]["history"][k].clear()
        analyzers[cid]["alerter"].clear()
    
    return jsonify({"success": success})

@app.route('/health', methods=['GET'])
def health_check():
    """Lightweight endpoint for Kubernetes readiness and liveness probes."""
    return jsonify({"status": "healthy"})

@app.route('/metrics', methods=['GET'])
def metrics():
    """Prometheus metrics endpoint for monitoring availability, requests, and risk stats."""
    if PROMETHEUS_AVAILABLE:
        try:
            PROMETHEUS_PERSON_COUNT.labels(camera='camera1').set(state['camera1']['stats'].get('person_count', 0))
            PROMETHEUS_PERSON_COUNT.labels(camera='camera2').set(state['camera2']['stats'].get('person_count', 0))
            PROMETHEUS_RISK_SCORE.labels(camera='camera1').set(state['camera1']['stats'].get('risk_score', 0))
            PROMETHEUS_RISK_SCORE.labels(camera='camera2').set(state['camera2']['stats'].get('risk_score', 0))
            return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"status": "healthy", "prometheus_enabled": False})

def _daily_report_job():
    """Background loop to generate and email PDF report at midnight."""
    import time, datetime, report_generator, notifier
    last_run_day = None
    while True:
        now = datetime.datetime.now()
        # Run at midnight (00:xx) once per day
        if now.hour == 0 and now.minute == 0 and last_run_day != now.day:
            print("[Scheduler] Generating Daily Midnight PDF Report...")
            try:
                pdf_path = report_generator.generate_pdf(video_source="Camera 1")
                notifier.send_email_alert(
                    "Daily Security Summary - VisionGuard",
                    "Attached is the daily security summary PDF report.",
                    [pdf_path] if pdf_path else None
                )
                last_run_day = now.day
                print("[Scheduler] [SUCCESS] Daily report sent.")
            except Exception as e:
                print(f"[Scheduler] [ERROR] Failed to send daily report: {e}")
        time.sleep(30)

if __name__ == '__main__':
    os.makedirs('frontend', exist_ok=True)

    print("Starting Flask server...")
    import threading
    threading.Thread(target=_daily_report_job, daemon=True).start()

    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", 5000)),
        debug=False,
        use_reloader=False,
        threaded=True
    )