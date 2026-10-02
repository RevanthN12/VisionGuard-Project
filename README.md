# VisionGuard — Intelligent Vision-Based Crowd Monitoring & Stampede Risk Prediction System (DevOps Enabled)

**Final-Year B.E. Computer Science and Engineering Project**

A real-time intelligent crowd monitoring and stampede risk prediction system integrated with a complete **DevOps & MLOps Pipeline**: **GitHub → Jenkins → Docker → Container Registry → Kubernetes → VisionGuard → Cloud Video Storage → Prometheus → Grafana**.

---

## 🛠️ Technology Stack & DevOps Integration

- **AI/ML Core**: Python 3.10, YOLOv8 (person & weapon detection), OpenCV (Farneback Optical Flow), PyTorch, SQLite.
- **Web App & Server**: Flask, HTML5/CSS3, JavaScript (WebSockets/MJPEG live streaming).
- **Source Control**: GitHub (`main` branch).
- **CI/CD Platform**: Jenkins (`Jenkinsfile` 11-stage automated pipeline).
- **Containerization**: Docker & Docker Compose (`Dockerfile`, `.dockerignore`, `docker-compose.yml`).
- **Container Storage**: Docker Hub / Private Registry.
- **Orchestration**: Kubernetes (`k8s/` manifests: Namespace, ConfigMap, Secrets, PV, PVC, Deployment, Service).
- **Evidence Storage**: Cloud/Object Storage Architecture (Video-Only Evidence Storage Policy: `.mp4` video clips saved to Cloudinary/S3; no permanent image snapshots).
- **Monitoring & Observability**: Prometheus (`/metrics` exporter) & Grafana (Crowd Safety & Infrastructure Dashboard).

---

## 🏗️ End-to-End DevOps Architecture

```text
                    GitHub
                       │
                       ▼
                    Jenkins (CI/CD Pipeline)
                       │
            ┌──────────┼──────────┐
            ▼          ▼          ▼
          Build       Test     Security
            │          │          │
            └──────────┼──────────┘
                       ▼
                  Docker Image
                       │
                       ▼
                Docker Registry (Docker Hub)
                       │
                       ▼
                  Kubernetes Cluster
                       │
              ┌────────┴────────┐
              ▼                 ▼
        VisionGuard Pod   VisionGuard Pod
              │                 │
              └────────┬────────┘
                       ▼
                VisionGuard AI
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
     YOLOv8        Risk Analysis    Alerts
        │              │
        └──────────────┘
               │
               ▼
     Processed Video Clip (.mp4)
               │
               ▼
      Cloud/Object Video Storage (Cloudinary/S3)
               │
               ▼
       Video URL + Metadata
               │
               ▼
            Database (SQLite)

               │
               ▼
       Prometheus + Grafana Monitoring (/metrics)
```

---

## 🎥 Video-Only Evidence Storage Architecture

VisionGuard strictly enforces a **VIDEO-ONLY Evidence Policy**:
- **Allowed**: Full-duration annotated video clips (`.mp4`) recording incidents when risk level exceeds `HIGH RISK` or `CRITICAL`.
- **Allowed**: Temporary OpenCV/YOLO in-memory frame processing.
- **Forbidden**: Saving permanent `.jpg` or `.png` frame screenshots to disk.

### Video Metadata Schema (Database & Cloud Storage):
```json
{
  "video_id": "VG-2026-001",
  "filename": "Camera_1_FULL_clip_HIGH_RISK_20261002_223000.mp4",
  "risk_level": "HIGH RISK",
  "risk_score": 87.5,
  "crowd_count": 42,
  "timestamp": "2026-10-02T22:30:00",
  "video_url": "https://res.cloudinary.com/demo/video/upload/visionguard_evidence/Camera_1_clip.mp4",
  "alert_status": "SENT"
}
```

---

## 📁 Project Structure

```text
VisionGuard_Project/
│
├── server.py               # Flask Web Server, API, & Prometheus exporter (/health, /metrics)
├── config.py               # Application configuration & risk weights
├── video_processor.py      # Multi-source video input (Webcam, Sample, Synthetic fallback)
├── detection.py            # YOLOv8 person detection & inference
├── crowd_count.py          # Person counter module
├── density.py              # Crowd density analyzer
├── movement.py             # Farneback optical flow movement analyzer
├── behavior_analysis.py    # Congestion & panic behavior detector
├── risk_predictor.py       # Stampede risk engine (0–100%)
├── alert.py                # Alert manager
├── evidence_recorder.py    # Video-only clip recorder (.mp4)
├── cloud_storage.py        # Cloud/Object video evidence uploader
├── database.py             # SQLite database manager
├── notifier.py             # Email (SMTP) & Telegram alert sender
├── requirements.txt        # Python dependency manifest
│
├── Dockerfile              # Production multi-stage Docker build
├── docker-compose.yml      # Local container orchestration
├── Jenkinsfile             # 11-Stage Jenkins CI/CD pipeline
├── .dockerignore           # Excluded container build files
├── .gitignore              # Excluded Git source files
├── .env.example            # Safe environment template
│
├── k8s/                    # Kubernetes Manifests
│   ├── namespace.yaml      # visionguard namespace
│   ├── configmap.yaml      # Non-sensitive configuration
│   ├── secret.example.yaml # Sensitive credentials template
│   ├── persistent-volume.yaml     # hostPath PV (DirectoryOrCreate)
│   ├── persistent-volume-claim.yaml # PV Claim (5Gi)
│   ├── deployment.yaml     # VisionGuard Deployment (Liveness & Readiness probes)
│   └── service.yaml        # Service exposure (LoadBalancer / NodePort)
│
├── monitoring/             # Prometheus & Grafana Configuration
│   ├── prometheus.yml      # Prometheus scrape job for /metrics
│   └── grafana/
│       ├── datasource.yml  # Auto-configured Prometheus datasource
│       └── visionguard_dashboard.json # Pre-built Grafana monitoring dashboard
│
├── tests/                  # Automated Pytest / Unittest Suite
│   └── test_api.py         # Tests for /health, /metrics, Risk engine, Video policy
│
├── models/                 # YOLOv8 PyTorch model files
├── database/               # SQLite database file
├── outputs/evidence/videos/# Processed evidence video clips (.mp4)
└── videos/sample_videos/   # Sample surveillance videos
```

---

## 🚀 Quick Start & Setup Guide

### 1. Local Development (Windows / Linux)
```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run unit tests
python -m unittest discover -s tests

# 3. Start Flask application
python server.py
```
👉 Access Dashboard at: **http://localhost:5000**

---

### 2. Docker & Docker Compose Setup
```powershell
# Build Docker Image locally
docker build -t visionguard:latest .

# Run single container
docker run -p 5000:5000 visionguard:latest

# Run with Docker Compose
docker compose up --build
```
👉 Access Dashboard at: **http://localhost:5000**

---

### 3. Kubernetes Deployment (Docker Desktop / Minikube)
```powershell
# Apply all Kubernetes manifests
kubectl apply -f k8s/

# Restart deployment to pull updated image
kubectl rollout restart deployment visionguard -n visionguard

# Verify Pod & Service status
kubectl get pods -n visionguard
kubectl get svc -n visionguard
```
👉 Access Dashboard at: **http://localhost:5000** *(or http://localhost:30000)*

---

### 4. Jenkins CI/CD Pipeline Setup
1. Create a new **Pipeline** job in Jenkins.
2. Select **Pipeline script from SCM** -> **Git**.
3. Repository URL: `https://github.com/RevanthN12/VisionGuard-Project.git`
4. Script Path: `Jenkinsfile`
5. Configure Jenkins Credentials:
   - `docker-hub-credentials` (Username & Password for Docker Hub)
   - `k8s-kubeconfig` (Kubernetes config)

#### Jenkins Pipeline 11 Stages:
1. **Checkout**: Pull code from GitHub `main`.
2. **Environment Validation**: Validate Python, Docker, and `kubectl`.
3. **Install Dependencies**: Install `requirements.txt`, `pytest`, `flake8`, `safety`.
4. **Run Tests**: Execute `pytest tests/`.
5. **Python Syntax Check**: Run `flake8` syntax validation.
6. **Security/Dependency Check**: Run `safety check`.
7. **Docker Build**: Build `visionguard:${BUILD_NUMBER}`.
8. **Docker Tagging**: Tag as `latest` and `${BUILD_NUMBER}`.
9. **Push Docker Image**: Push to Docker Registry / Docker Hub.
10. **Kubernetes Deployment**: Apply `k8s/` manifests and update deployment.
11. **Deployment Verification**: Verify rollout status and pod health.

---

### 5. Prometheus & Grafana Setup
```powershell
# Run Prometheus & Grafana locally or in Docker
docker run -d --name prometheus -p 9090:9090 -v ${PWD}/monitoring/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus
docker run -d --name grafana -p 3000:3000 grafana/grafana
```
- **Prometheus Metrics**: `http://localhost:5000/metrics`
- **Prometheus UI**: `http://localhost:9090`
- **Grafana UI**: `http://localhost:3000` (Import `monitoring/grafana/visionguard_dashboard.json`)

---

## 🧪 Testing Matrix & Validation Summary

| Test Case | Tool / Command | Result |
|-----------|----------------|--------|
| Health Endpoint | `GET /health` | **PASS** (`{"status": "healthy"}`) |
| Prometheus Exporter | `GET /metrics` | **PASS** (Prometheus format) |
| Risk Prediction Engine | `python -m unittest tests/test_api.py` | **PASS** (Weighted formula verified) |
| Video-Only Evidence | `test_video_only_evidence_policy` | **PASS** (Zero `.jpg`/`.png` saved) |
| Docker Container Build | `docker build -t visionguard:latest .` | **PASS** |
| Kubernetes Orchestration | `kubectl get pods -n visionguard` | **PASS** (`1/1 Ready - Running`) |
| Jenkins CI/CD Pipeline | `Jenkinsfile` (11 stages) | **PASS** |

---

## 🎓 Viva Explanation & Architecture Summary

> **"GitHub → Jenkins → Docker → Registry → Kubernetes → VisionGuard → Video Cloud Storage → Prometheus → Grafana"**

- **YOLOv8 + OpenCV**: Performs real-time object detection, optical flow movement tracking, and stampede risk estimation.
- **Docker**: Packages the application into an immutable container image.
- **Jenkins**: Automates the 11-stage CI/CD pipeline upon code push.
- **Docker Registry**: Stores versioned Docker images.
- **Kubernetes**: Manages container scheduling, self-healing restarts, PVC persistence, and load-balanced networking.
- **Cloud Video Storage**: Receives uploaded `.mp4` evidence video clips asynchronously.
- **Prometheus & Grafana**: Monitors application health, request throughput, and real-time crowd risk metrics.
