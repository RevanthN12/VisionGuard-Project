# Vision Guard — AI-Driven Stampede Prediction

**Final-Year B.E. Computer Science and Engineering Project**

A real-time intelligent crowd monitoring and stampede risk prediction system using Python, YOLOv8, OpenCV, Farneback Optical Flow, and Streamlit.

---

## 🚀 Quick Start (Windows)

```powershell
# 1. Navigate to project folder
cd "c:\Users\user\Desktop\p!"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the Flask backend
python server.py
```

The dashboard opens at **http://localhost:5000**

---

## 📁 Project Structure

```
p!/
├── server.py               # Flask backend & Web server (main entry)
├── config.py               # All configurable settings
├── video_processor.py      # Multi-source video input
├── detection.py            # YOLOv8n person detection
├── crowd_count.py          # Session crowd counting
├── density.py              # Crowd density analysis
├── movement.py             # Farneback optical flow
├── behavior_analysis.py    # Abnormal behavior detection
├── risk_predictor.py       # Stampede risk prediction
├── alert.py                # Alert manager
├── evidence_recorder.py    # Auto-save screenshots/clips
├── violence_detection.py   # Motion-heuristic aggression detection
├── weapon_detection.py     # Custom YOLO weapon detection
├── database.py             # SQLite DBMS
├── report_generator.py     # CSV/PDF reports
├── requirements.txt
│
├── models/
│   ├── yolov8n.pt          # Person detection (auto-downloaded)
│   └── weapon_best.pt      # Optional custom weapon model
│
├── database/
│   └── vision_guard.db     # Auto-created SQLite database
│
├── outputs/
│   ├── evidence/images/    # Auto-saved incident screenshots
│   ├── evidence/videos/    # Auto-saved incident clips
│   └── reports/            # Generated CSV/PDF reports
│
└── videos/sample_videos/   # Place sample videos here
```

---

## 🎯 Project Objectives

1. Develop a real-time AI-based crowd monitoring system using video surveillance
2. Detect and count people accurately using YOLOv8 and OpenCV
3. Estimate crowd density levels: LOW / MEDIUM / HIGH / CRITICAL
4. Analyze crowd movement and identify abnormal behavior
5. Predict stampede risks and generate real-time alerts

---

## 🔬 Risk Formula

```
Risk Score =
    Density Score    × 0.35
  + Movement Score   × 0.25
  + Behavior Score   × 0.20
  + Congestion Score × 0.10
  + Threat Score     × 0.10
```

| Score  | Level     |
|--------|-----------|
| 0–29   | ✅ SAFE     |
| 30–49  | ⚠️ CAUTION  |
| 50–69  | 🚨 WARNING  |
| 70–84  | 🔴 HIGH RISK|
| 85–100 | 💀 CRITICAL |

---

## 🛠️ Customizing the Project

If you want to customize or make changes to this project, the codebase is modular and very easy to adjust. Here are the main areas you can tweak depending on what you want to achieve:

### 1. The Configuration File (`config.py`)
This is the most important file for tuning the system without writing new code. You can edit this file to:
- **Change Risk Thresholds:** Adjust what counts as "HIGH RISK" or "CRITICAL".
- **Tune Detection Sensitivity:** Lower or raise `YOLO_CONF` (currently `0.20`) if the AI is detecting too many or too few people.
- **Adjust Weights:** Modify how much density, movement, or behavior contributes to the overall risk score (`RISK_W_DENSITY`, `RISK_W_MOVEMENT`, etc.).
- **Enable/Disable External Alerts:** Toggle `EXTERNAL_ALERTS_ENABLED = True / False` or change the WhatsApp/Email target numbers.

### 2. The Alert System (`alert.py` & `notifier.py`)
If you want to change how the system notifies you:
- Open `notifier.py` to add new notification methods (like sending an SMS via Twilio, a Telegram message, or a Slack webhook) instead of just WhatsApp and Email.
- Open `alert.py` to change the logic of when sounds play or how often alerts are allowed to trigger (cooldowns).

### 3. The Dashboard UI (`templates/` & `static/`)
If you want to change the look and feel of the web dashboard:
- Look in the `templates/` folder (likely contains `index.html`) to change the HTML layout.
- Look in the `static/` folder (contains `style.css` and `script.js`) to change colors, animations, or how the charts are drawn on the screen.

### 4. Custom AI Models (`models/`)
Right now, the system uses `yolov8n.pt` for detecting people. If you train a better, custom YOLO model on a specific dataset (for example, for a top-down camera view), you can just drop your `.pt` model file into the `models/` folder and update the path in `config.py`.
