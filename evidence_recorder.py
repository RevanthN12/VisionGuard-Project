"""
evidence_recorder.py — Vision Guard Evidence Recording Module
Saves annotated screenshots and records FULL DURATION video clips for the entire duration 
of HIGH RISK or CRITICAL incidents.
"""

import cv2
import os
import time
import datetime
import config


class EvidenceRecorder:
    """Auto-saves annotated screenshots and full-duration video clips during High Risk incidents."""

    def __init__(self):
        self._writer = None
        self._recording = False
        self._current_clip = None
        self._last_img_time = 0
        self._frame_count = 0
        self._frames_remaining = 0
        self._recording_fps = config.EVIDENCE_FPS

    # ── Public API ────────────────────────────────────────────────────────────

    def maybe_save(self, frame, risk_result: dict, density_result: dict,
                   movement_result: dict, person_count: int, camera_label: str = "Camera 1") -> str | None:
        """
        Save a screenshot if risk level is HIGH RISK or CRITICAL.
        Returns the relative path of the saved image, or None.
        """
        level = risk_result.get("level", "SAFE")
        if level not in ("HIGH RISK", "CRITICAL"):
            return None

        now = time.time()
        if (now - self._last_img_time) < 5:
            return None
        self._last_img_time = now

        annotated = self._annotate(frame.copy(), risk_result, density_result, movement_result, person_count, camera_label)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        cam_prefix = camera_label.replace(' ', '_')
        filename = f"{cam_prefix}_{level.replace(' ','_')}_{ts}.jpg"
        filepath = os.path.join(config.EVIDENCE_IMG_DIR, filename)

        try:
            cv2.imwrite(filepath, annotated)
            print(f"[Evidence] [SNAPSHOT_SAVED] High Risk Snapshot Saved: {filepath}")
            return filepath
        except Exception as e:
            print(f"[Evidence] Save error: {e}")
            return None

    def start_clip(self, frame, level: str, camera_label: str = "Camera 1", fps: float = 25.0):
        """Begin recording a FULL DURATION evidence video clip at 1.0x normal speed."""
        if self._recording:
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        cam_prefix = camera_label.replace(' ', '_')
        fn = f"{cam_prefix}_FULL_clip_{level.replace(' ','_')}_{ts}.mp4"
        self._current_clip = os.path.join(config.EVIDENCE_VID_DIR, fn)
        h, w = frame.shape[:2]

        self._recording_fps = fps if (fps and fps > 0) else config.EVIDENCE_FPS
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(
            self._current_clip, fourcc,
            self._recording_fps, (w, h)
        )
        self._recording = True
        self._clip_start_time = time.time()
        self._frame_count = 0
        self._frames_remaining = int(self._recording_fps * config.EVIDENCE_CLIP_SEC)
        print(f"[Evidence] [VIDEO_START] Started FULL DURATION High Risk Video Recording: {self._current_clip} at {self._recording_fps:.1f} FPS")

    def write_frame(self, frame, is_high_risk: bool = True):
        """Write frame continuously to active full-duration video clip. Stops automatically when duration ends."""
        if not self._recording or self._writer is None:
            return
        
        self._writer.write(frame)
        self._frame_count += 1
        
        if is_high_risk:
            # Reset the countdown if risk is still high
            self._frames_remaining = int(self._recording_fps * config.EVIDENCE_CLIP_SEC)
        else:
            self._frames_remaining -= 1
            
        if self._frames_remaining <= 0:
            self.stop_clip()

    def stop_clip(self):
        """Finish recording and flush full-duration video clip to disk at 1.0x normal speed."""
        if not self._recording and self._writer is None:
            return

        if self._writer:
            self._writer.release()
            self._writer = None
        self._recording = False
        
        clip_duration = max(time.time() - getattr(self, "_clip_start_time", time.time()), 0.5)
        actual_fps = max(self._frame_count / clip_duration, 1.0)
        print(f"[Evidence] [VIDEO_STOP] Finished Evidence Clip ({self._frame_count} frames over {clip_duration:.1f}s = {actual_fps:.1f} FPS): {self._current_clip}")

        if self._current_clip and os.path.exists(self._current_clip):
            import threading
            def convert(filepath, true_fps):
                try:
                    import subprocess
                    import time
                    from imageio_ffmpeg import get_ffmpeg_exe

                    time.sleep(0.5)
                    if os.path.getsize(filepath) < 1000:
                        return

                    ffmpeg = get_ffmpeg_exe()
                    temp_path = filepath + ".h264.mp4"
                    # Re-time timestamps so video plays at true 1.0x normal real-time speed in all browsers
                    result = subprocess.run([
                        ffmpeg, "-y",
                        "-i", filepath,
                        "-vf", f"setpts=N/({true_fps:.2f}*TB)",
                        "-r", "25",
                        "-vcodec", "libx264",
                        "-pix_fmt", "yuv420p",
                        "-preset", "ultrafast",
                        temp_path
                    ], capture_output=True, text=True)

                    if result.returncode == 0 and os.path.exists(temp_path) and os.path.getsize(temp_path) > 1000:
                        os.replace(temp_path, filepath)
                        print(f"[Evidence] [ENCODED] Normal 1.0x speed video ready: {filepath}")
                except Exception as e:
                    print(f"[Evidence] FFmpeg conversion error: {e}")
            threading.Thread(target=convert, args=(self._current_clip, actual_fps), daemon=True).start()

    def list_evidence(self, limit: int = 50) -> list:
        """Return most recent evidence items (images and videos) with date, time, and camera metadata."""
        try:
            images = [f for f in os.listdir(config.EVIDENCE_IMG_DIR) if f.endswith(".jpg")]
            videos = [f for f in os.listdir(config.EVIDENCE_VID_DIR) if f.endswith(".mp4")]

            combined = []
            for f in images:
                cam = "Camera 2" if f.startswith("Camera_2") else "Camera 1"
                filepath = os.path.join(config.EVIDENCE_IMG_DIR, f)
                mtime = os.path.getmtime(filepath)
                dt = datetime.datetime.fromtimestamp(mtime)
                combined.append({
                    "name": f,
                    "type": "image",
                    "camera": cam,
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M:%S"),
                    "datetime_formatted": dt.strftime("%d %b %Y, %I:%M:%S %p"),
                    "timestamp": mtime
                })

            for f in videos:
                cam = "Camera 2" if f.startswith("Camera_2") else "Camera 1"
                filepath = os.path.join(config.EVIDENCE_VID_DIR, f)
                mtime = os.path.getmtime(filepath)
                dt = datetime.datetime.fromtimestamp(mtime)
                combined.append({
                    "name": f,
                    "type": "video",
                    "camera": cam,
                    "date": dt.strftime("%Y-%m-%d"),
                    "time": dt.strftime("%H:%M:%S"),
                    "datetime_formatted": dt.strftime("%d %b %Y, %I:%M:%S %p"),
                    "timestamp": mtime
                })

            combined = sorted(combined, key=lambda x: x["timestamp"], reverse=True)
            return combined[:limit]
        except Exception as e:
            print(f"[Evidence] Error listing evidence: {e}")
            return []

    # ── Internal ──────────────────────────────────────────────────────────────

    def _annotate(self, frame, risk, density, movement, count, camera_label: str = "Camera 1") -> object:
        h, w = frame.shape[:2]
        banner = 52
        cv2.rectangle(frame, (0, h - banner), (w, h), (10, 10, 15), -1)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lvl = risk.get("level", "?")
        scr = risk.get("score", 0)
        line1 = f"[{camera_label}] {ts} | Risk: {lvl} ({scr:.0f}%) | People: {count}"
        line2 = (f"Density:{density.get('density_score',0):.0f}% "
                 f"Movement:{movement.get('speed',0):.1f}px/f "
                 f"Turbulence:{movement.get('turbulence',0):.1f}")
        cv2.putText(frame, line1, (8, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255) if lvl in ("HIGH RISK", "CRITICAL") else (255, 255, 255), 1)
        cv2.putText(frame, line2, (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1)
        return frame
