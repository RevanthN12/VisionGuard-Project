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
            # Fallback to any valid sample video
            samples = self.get_sample_videos()
            if samples:
                path = os.path.join(config.SAMPLE_VIDEOS_DIR, samples[0])
                if not os.path.exists(path):
                    path = os.path.join(config.BASE_DIR, samples[0])

        if not os.path.exists(path):
            print(f"[VideoProcessor] Sample not found: {filename}")
            return False

        return self._open(path, self.SOURCE_SAMPLE)

    def read_frame(self):
        """
        Read the next frame.
        Returns (success: bool, frame: ndarray | None).
        Handles looping for file sources and 1.0x real-time speed throttling.
        """
        if self.cap is None or not self.cap.isOpened():
            self.is_open = False
            return False, None

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
            return False, None

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
        try:
            if isinstance(source, int) or (isinstance(source, str) and str(source).isdigit()):
                # Prioritize DSHOW on Windows for better compatibility
                self.cap = cv2.VideoCapture(int(source), cv2.CAP_DSHOW)
                if not self.cap.isOpened():
                    self.cap = cv2.VideoCapture(int(source))
            else:
                self.cap = cv2.VideoCapture(source)

            if not self.cap.isOpened():
                print(f"[VideoProcessor] Cannot open source: {source}")
                self.cap = None
                self.is_open = False
                return False

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
