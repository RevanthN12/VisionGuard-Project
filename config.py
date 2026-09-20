import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"

# ── Project root ────────────────────────────────────────────────────────────

# ── Project root ────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Model paths ─────────────────────────────────────────────────────────────
MODEL_YOLO        = os.path.join(BASE_DIR, "models", "yolov8n.pt")
MODEL_WEAPON      = os.path.join(BASE_DIR, "models", "weapon_best.pt")
MODEL_VIOLENCE    = os.path.join(BASE_DIR, "models", "violence_model")

# ── Database ────────────────────────────────────────────────────────────────
DB_PATH           = os.path.join(BASE_DIR, "database", "vision_guard.db")

# ── Output folders ──────────────────────────────────────────────────────────
EVIDENCE_IMG_DIR  = os.path.join(BASE_DIR, "outputs", "evidence", "images")
EVIDENCE_VID_DIR  = os.path.join(BASE_DIR, "outputs", "evidence", "videos")
REPORTS_DIR       = os.path.join(BASE_DIR, "outputs", "reports")
PROCESSED_VID_DIR = os.path.join(BASE_DIR, "outputs", "processed_videos")
SOUNDS_DIR        = os.path.join(BASE_DIR, "sounds")
SAMPLE_VIDEOS_DIR = os.path.join(BASE_DIR, "videos", "sample_videos")

# ── YOLO inference ──────────────────────────────────────────────────────────
YOLO_CONF         = 0.20        # Confidence threshold
YOLO_IMGSZ        = 320         # Optimized 320px inference size for 10x faster real-time CPU FPS
YOLO_CLASSES      = [0, 24, 26, 28]         # 0=person, 24=backpack, 26=handbag, 28=suitcase
FRAME_SKIP        = 1           # Process every frame for smooth real-time video

# ── Video Settings (1.0x Real-time Normal Speed) ─────────────────────────────
FRAME_WIDTH       = 640
FRAME_HEIGHT      = 480
TARGET_FPS        = 25.0        # Standard 25 FPS normal video speed

# ── Density thresholds (people per frame) ───────────────────────────────────
DENSITY_LOW       = 0.20        # 0–20% occupancy  → LOW
DENSITY_MEDIUM    = 0.45        # 20–45%           → MEDIUM
DENSITY_HIGH      = 0.65        # 45–65%           → HIGH
                                # >65%             → CRITICAL

# ── Movement thresholds (optical-flow magnitude, pixels/frame) ──────────────
MOVE_LOW          = 1.5
MOVE_MEDIUM       = 4.0
MOVE_HIGH         = 8.0
MOVE_PANIC        = 12.0        # Panic / stampede threshold

# ── Risk predictor weights ───────────────────────────────────────────────────
RISK_W_DENSITY    = 0.30
RISK_W_MOVEMENT   = 0.30
RISK_W_BEHAVIOR   = 0.20
RISK_W_CONGESTION = 0.10
RISK_W_THREAT     = 0.10

# ── Risk level thresholds (0–100) ────────────────────────────────────────────
RISK_SAFE         = 30
RISK_CAUTION      = 50
RISK_WARNING      = 70
RISK_HIGH         = 85

# ── Alert cooldown (seconds between repeated alerts per level) ───────────────
ALERT_COOLDOWN    = {
    "CAUTION":   10,
    "WARNING":   5,
    "HIGH RISK":  2,
    "CRITICAL":   1,
}

# ── Congestion detection ──────────────────────────────────────────────────────
CONGESTION_FRAMES = 30          # Consecutive frames of HIGH density = congested

# ── Evidence recording (Normal Speed Video Clip) ──────────────────────────────
EVIDENCE_MIN_RISK = "HIGH RISK"   # Minimum risk level to save evidence
EVIDENCE_CLIP_SEC = 5           # Video clip duration in seconds
EVIDENCE_FPS      = 25.0        # 25 FPS matching normal real-time video playback

# ── Report ────────────────────────────────────────────────────────────────────
REPORT_CSV_PATH   = os.path.join(REPORTS_DIR, "session_report.csv")

# ── Ensure all output directories exist ──────────────────────────────────────
for _d in [EVIDENCE_IMG_DIR, EVIDENCE_VID_DIR, REPORTS_DIR,
           PROCESSED_VID_DIR, SOUNDS_DIR, SAMPLE_VIDEOS_DIR,
           os.path.dirname(DB_PATH)]:
    os.makedirs(_d, exist_ok=True)

# -- External Alerts ----------------------------------------------------------
EXTERNAL_ALERTS_ENABLED = True
EXTERNAL_ALERT_LEVELS = {'HIGH RISK', 'CRITICAL'}
