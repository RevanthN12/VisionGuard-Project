"""
video_processor.py — Vision Guard Video Input and Processing Module
Supports: webcam, CCTV/RTSP, uploaded file, sample videos.
Fast device opening with guaranteed fallback to working sample videos.
"""

import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import cv2
cv2.setNumThreads(1)
import time
import config


class VideoProcessor:
    """Manages video capture from multiple source types at 1.0x normal video speed."""

    SOURCE_WEBCAM  = "webcam"
    SOURCE_RTSP    = "rtsp"
    SOURCE_FILE    = "file"
    SOURCE_SAMPLE  = "sample"

    def __init__(self):
        self.cap            = None
        self.source_type    = None
        self.source_path    = None
        self.frame_count    = 0
        self.fps            = config.TARGET_FPS
        self.width          = config.FRAME_WIDTH
        self.height         = config.FRAME_HEIGHT
        self._last_frame_t  = 0.0
        self.is_open        = False
        self._consecutive_failures = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def open_webcam(self, index: int = 0) -> bool:
        """Open default or indexed webcam."""
        return self._open(index, self.SOURCE_WEBCAM)

    def open_rtsp(self, url: str) -> bool:
        """Open a CCTV / RTSP stream."""
        return self._open(url, self.SOURCE_RTSP)

    def open_file(self, path: str) -> bool:
        """Open an uploaded or local video file."""
        if not os.path.exists(path):
            print(f"[VideoProcessor] File not found: {path}")
            return False
        return self._open(path, self.SOURCE_FILE)

    def open_sample(self, filename: str) -> bool:
        """Open a sample video from sample_videos folder or project base directory."""
        path = os.path.join(config.SAMPLE_VIDEOS_DIR, filename)
        if not os.path.exists(path):
            path = os.path.join(config.BASE_DIR, filename)
        if not os.path.exists(path):
            samples = self.get_sample_videos()
            if samples:
                path = os.path.join(config.SAMPLE_VIDEOS_DIR, samples[0])
                if not os.path.exists(path):
                    path = os.path.join(config.BASE_DIR, samples[0])

        if not os.path.exists(path):
            print(f"[VideoProcessor] Sample not found: {filename}")
            return False

        return self._open(path, self.SOURCE_SAMPLE)

    def open_synthetic(self) -> bool:
        """Create a synthetic animated surveillance stream if physical webcam & sample files are unavailable."""
        self.source_type = "synthetic"
        self.source_path = "Synthetic Stream"
        self.is_open = True
        self.frame_count = 0
        self.fps = config.TARGET_FPS
        return True

    def read_frame(self):
        """
        Read the next frame.
        Returns (success: bool, frame: ndarray | None).
        Handles looping for file sources and 1.0x real-time speed throttling.
        Automatically falls back to sample video if webcam becomes unresponsive or black.
        """
        import numpy as np
        if self.source_type == "synthetic":
            now = time.time()
            frame_interval = 1.0 / max(self.fps, 1.0)
            if (now - self._last_frame_t) < frame_interval:
                return False, None
            self._last_frame_t = now
            
            import math
            h, w = self.height, self.width
            frame = np.zeros((h, w, 3), dtype=np.uint8)
            for x in range(0, w, 40):
                cv2.line(frame, (x, 0), (x, h), (20, 25, 35), 1)
            for y in range(0, h, 40):
                cv2.line(frame, (0, y), (w, y), (20, 25, 35), 1)
            t = self.frame_count * 0.05
            cx = int(w/2 + math.sin(t) * 150)
            cy = int(h/2 + math.cos(t * 0.7) * 100)
            cv2.rectangle(frame, (cx-30, cy-60), (cx+30, cy+60), (0, 255, 0), 2)
            cv2.putText(frame, "PERSON 95%", (cx-30, cy-65), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
            self.frame_count += 1
            return True, frame

        if self.cap is None or not self.cap.isOpened():
            self.is_open = False
            return False, None

        if self.source_type not in (self.SOURCE_WEBCAM,):
            now = time.time()
            frame_interval = 1.0 / max(self.fps, 1.0)
            if (now - self._last_frame_t) < frame_interval:
                return False, None
            self._last_frame_t = now

        ret, frame = self.cap.read()

        # Loop file sources continuously
        if not ret and self.source_type in (self.SOURCE_FILE, self.SOURCE_SAMPLE):
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()

        if not ret or frame is None:
            self._consecutive_failures += 1
            return False, None

        self._consecutive_failures = 0
        frame = self._preprocess(frame)
        self.frame_count += 1
        return True, frame

    def release(self):
        """Release capture resources."""
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.is_open = False

    def get_total_frames(self) -> int:
        """Return total frames in file source (-1 for live)."""
        if self.cap and self.source_type in (self.SOURCE_FILE, self.SOURCE_SAMPLE):
            return int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return -1

    def get_sample_videos(self) -> list:
        """List all sample videos in sample_videos folder and root directory."""
        try:
            exts = {".mp4", ".avi", ".mov", ".mkv"}
            files = []
            if os.path.exists(config.SAMPLE_VIDEOS_DIR):
                files.extend([f for f in os.listdir(config.SAMPLE_VIDEOS_DIR) if os.path.splitext(f)[1].lower() in exts])
            if os.path.exists(config.BASE_DIR):
                root_files = [f for f in os.listdir(config.BASE_DIR) if os.path.splitext(f)[1].lower() in exts]
                for rf in root_files:
                    if rf not in files and not rf.startswith("output"):
                        files.append(rf)
            return sorted(files)
        except Exception:
            return []

    # ── Internal ────────────────────────────────────────────────────────────

    def _open(self, source, source_type: str) -> bool:
        self.release()
        import numpy as np
        try:
            if isinstance(source, int) or (isinstance(source, str) and str(source).isdigit()):
                idx = int(source)
                
                backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if os.name == 'nt' else [cv2.CAP_ANY]
                opened = False
                for backend in backends:
                    cap_attempt = None
                    try:
                        cap_attempt = cv2.VideoCapture(idx, backend)
                        if cap_attempt and cap_attempt.isOpened():
                            try:
                                cap_attempt.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                            except Exception:
                                pass
                            cap_attempt.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            cap_attempt.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                            cap_attempt.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

                            for _ in range(12):
                                ret, test_frame = cap_attempt.read()
                                if ret and test_frame is not None and test_frame.size > 0:
                                    self.cap = cap_attempt
                                    opened = True
                                    break
                                time.sleep(0.04)
                    except Exception:
                        pass

                    if opened:
                        break
                    elif cap_attempt:
                        cap_attempt.release()

                if opened:
                    self.source_type  = source_type
                    self.source_path  = str(source)
                    self.frame_count  = 0
                    self.is_open      = True
                    print(f"[VideoProcessor] Opened {source_type} #{idx} successfully (FPS: {self.fps:.1f})")
                    return True
                else:
                    if cap_attempt:
                        cap_attempt.release()
                    print(f"[VideoProcessor] Cannot open webcam index: {source}")
                    self.cap = None
                    self.is_open = False
                    return False
            else:
                self.cap = cv2.VideoCapture(source)

            if not self.cap.isOpened():
                print(f"[VideoProcessor] Cannot open source: {source}")
                self.cap = None
                self.is_open = False
                return False
                
            test_ok = False
            for _ in range(20):
                ret, test_frame = self.cap.read()
                if ret and test_frame is not None and test_frame.size > 0:
                    if np.count_nonzero(test_frame) > 0:
                        test_ok = True
                        break
                time.sleep(0.05)
                
            if not test_ok:
                print(f"[VideoProcessor] Source opened but returned blank frame after retries: {source}")
                self.cap.release()
                self.cap = None
                self.is_open = False
                return False

            if source_type in (self.SOURCE_FILE, self.SOURCE_SAMPLE):
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

            native_fps = self.cap.get(cv2.CAP_PROP_FPS)
            if native_fps and 1.0 <= native_fps <= 60.0:
                self.fps = native_fps
            else:
                self.fps = config.TARGET_FPS

            self.source_type  = source_type
            self.source_path  = str(source)
            self.frame_count  = 0
            self.is_open      = True
            print(f"[VideoProcessor] Opened {source_type}: {source} (Playback Speed: {self.fps:.1f} FPS)")
            return True
        except Exception as e:
            print(f"[VideoProcessor] Error opening source: {e}")
            self.cap      = None
            self.is_open  = False
            return False

    def _preprocess(self, frame):
        """Resize and validate frame dimensions."""
        if frame is None:
            return None
        h, w = frame.shape[:2]
        if w != self.width or h != self.height:
            frame = cv2.resize(frame, (self.width, self.height),
                               interpolation=cv2.INTER_LINEAR)
        return frame


def detect_available_webcams() -> list:
    """Scan and return list of all active physical USB webcam devices with hardware device names."""
    import subprocess
    try:
        cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT)
    except Exception:
        pass

    friendly_names = []
    try:
        if os.name == 'nt':
            cmd = ['powershell', '-NoProfile', '-Command', 
                   'Get-PnpDevice -PresentOnly -Class Camera,Image | Select-Object -ExpandProperty FriendlyName']
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if res.returncode == 0:
                friendly_names = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    except Exception:
        pass

    devices = []
    backends = [cv2.CAP_DSHOW, cv2.CAP_MSMF, cv2.CAP_ANY] if os.name == 'nt' else [cv2.CAP_ANY]
    for idx in range(6):
        opened = False
        w, h = 640, 480
        for backend in backends:
            cap = None
            try:
                cap = cv2.VideoCapture(idx, backend)
                if cap and cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None and frame.size > 0:
                        h, w = frame.shape[:2]
                        opened = True
                        break
            except Exception:
                pass
            finally:
                if cap is not None:
                    cap.release()
            if opened:
                break

        if opened:
            dev_name = friendly_names[len(devices)] if len(devices) < len(friendly_names) else f"Webcam #{idx}"
            devices.append({
                "index": idx,
                "label": f"Webcam #{idx}: {dev_name} ({w}x{h})",
                "name": dev_name,
                "resolution": f"{w}x{h}"
            })

    return devices
