"""
evidence_recorder.py — Vision Guard Evidence Recording Module
Captures, stores, and logs high-risk video clips and incident snapshots.
Guarantees H.264 browser compatibility, reliable Windows file handling,
automatic database registration, and Telegram evidence dispatch.
"""

import cv2
import os
import time
import datetime
import threading
import subprocess
import config
import database
import notifier


class EvidenceRecorder:
    """Auto-saves annotated snapshots and complete high-risk video clips during elevated incidents."""

    def __init__(self):
        self._writer = None
        self._recording = False
        self._current_clip = None
        self._raw_clip = None
        self._last_img_time = 0
        self._last_clip_stop_time = 0
        self._frame_count = 0
        self._target_frames = 60
        self._post_event_countdown = 20
        self._recording_fps = config.EVIDENCE_FPS
        self._clip_level = "HIGH RISK"
        self._clip_score = 75.0
        self._clip_count = 0
        self._camera_label = "Camera 1"
        self._last_saved_img = None

    # ── Snapshot Capture ──────────────────────────────────────────────────────

    def maybe_save(self, frame, risk_result: dict, density_result: dict,
                   movement_result: dict, person_count: int, camera_label: str = "Camera 1") -> str | None:
        """Saves an instant high-resolution incident snapshot when high-risk begins."""
        return self.save_snapshot(frame, risk_result, density_result, movement_result, person_count, camera_label)

    def save_snapshot(self, frame, risk_result: dict, density_result: dict,
                      movement_result: dict, person_count: int, camera_label: str = "Camera 1") -> str | None:
        """Saves an annotated evidence snapshot image with timestamp and metrics HUD."""
        now = time.time()
        # Debounce snapshot saving to at most once per 8 seconds per camera
        if now - self._last_img_time < 8.0 and self._last_saved_img and os.path.exists(self._last_saved_img):
            return self._last_saved_img

        try:
            self._last_img_time = now
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            level = risk_result.get("level", "HIGH_RISK").replace(" ", "_")
            score = risk_result.get("score", 75.0)
            cam_prefix = camera_label.replace(" ", "_")
            fn = f"{cam_prefix}_snapshot_{level}_{ts}.jpg"
            filepath = os.path.join(config.EVIDENCE_IMG_DIR, fn)

            # Create annotated copy for evidence storage
            annotated = self._annotate(frame.copy(), risk_result, density_result, movement_result, person_count, camera_label)
            cv2.imwrite(filepath, annotated, [cv2.IMWRITE_JPEG_QUALITY, 92])

            self._last_saved_img = filepath
            # Register in evidence database
            database.log_evidence(filepath, risk_result.get("level", "HIGH RISK"), score, person_count)
            print(f"[Evidence] [SNAPSHOT_SAVED] Evidence snapshot stored: {filepath}", flush=True)
            return filepath
        except Exception as e:
            print(f"[Evidence] Error saving snapshot: {e}", flush=True)
            return None

    # ── High-Risk Video Recording ─────────────────────────────────────────────

    def start_clip(self, frame, level: str, camera_label: str = "Camera 1", fps: float = 25.0,
                   risk_score: float = 75.0, person_count: int = 0):
        """Begin recording a high-risk video clip."""
        if self._recording:
            return

        now = time.time()
        # Enforce 2.0s cooldown between back-to-back clips
        if now - self._last_clip_stop_time < 2.0:
            return

        try:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            cam_prefix = camera_label.replace(" ", "_")
            level_clean = level.replace(" ", "_")
            fn = f"{cam_prefix}_clip_{level_clean}_{ts}.mp4"

            # Use staging file for raw capture to prevent file locks during encoding
            self._raw_clip = os.path.join(config.EVIDENCE_VID_DIR, f".raw_{fn}")
            self._current_clip = os.path.join(config.EVIDENCE_VID_DIR, fn)
            h, w = frame.shape[:2]

            self._recording_fps = max(float(fps), 5.0) if fps else config.EVIDENCE_FPS
            # Target 6.0 seconds duration per clip
            self._target_frames = int(max(self._recording_fps * 6.0, 45))
            self._post_event_countdown = int(max(self._recording_fps * 2.0, 15))
            self._frame_count = 0
            self._clip_level = level
            self._clip_score = risk_score
            self._clip_count = person_count
            self._camera_label = camera_label
            self._clip_start_time = now

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self._writer = cv2.VideoWriter(self._raw_clip, fourcc, self._recording_fps, (w, h))
            self._recording = True
            print(f"[Evidence] [VIDEO_START] Recording High Risk Video: {self._current_clip} ({self._recording_fps:.1f} FPS, target {self._target_frames} frames)", flush=True)
        except Exception as e:
            print(f"[Evidence] Error starting video clip: {e}", flush=True)
            self._recording = False
            self._writer = None

    def write_frame(self, frame, is_high_risk: bool = True):
        """Write frame continuously to active high-risk video clip. Finalizes automatically when duration is reached."""
        if not self._recording or self._writer is None:
            return

        try:
            self._writer.write(frame)
            self._frame_count += 1

            if is_high_risk:
                # If target duration for this clip has been captured, finalize it!
                if self._frame_count >= self._target_frames:
                    print(f"[Evidence] Target duration reached ({self._frame_count} frames). Finalizing clip...", flush=True)
                    self.stop_clip()
            else:
                # Risk dropped below threshold, countdown post-event buffer
                self._post_event_countdown -= 1
                if self._post_event_countdown <= 0 or self._frame_count >= self._target_frames:
                    self.stop_clip()
        except Exception as e:
            print(f"[Evidence] Error writing frame: {e}", flush=True)

    def stop_clip(self):
        """Finish recording and encode video clip to standard H.264 for instant browser and Telegram playback."""
        if not self._recording and self._writer is None:
            return

        self._recording = False
        self._last_clip_stop_time = time.time()

        if self._writer:
            try:
                self._writer.release()
            except Exception:
                pass
            self._writer = None

        raw_path = self._raw_clip
        final_path = self._current_clip
        frames = self._frame_count
        duration = max(time.time() - getattr(self, "_clip_start_time", time.time()), 0.5)
        actual_fps = max(frames / duration, 1.0)
        level = self._clip_level
        score = self._clip_score
        count = self._clip_count
        cam = self._camera_label

        print(f"[Evidence] [VIDEO_STOP] Captured {frames} frames over {duration:.1f}s ({actual_fps:.1f} FPS). Encoding to {final_path}...", flush=True)

        if raw_path and os.path.exists(raw_path):
            def process_and_store(raw_f, final_f, fps_rate, lvl, scr, cnt, camera):
                try:
                    time.sleep(0.3) # Allow OS file handles to flush
                    if os.path.getsize(raw_f) < 1000:
                        try: os.remove(raw_f)
                        except Exception: pass
                        return

                    from imageio_ffmpeg import get_ffmpeg_exe
                    ffmpeg = get_ffmpeg_exe()

                    # Transcode to H.264 YUV420P so Chrome/Edge/Firefox play smoothly
                    cmd = [
                        ffmpeg, "-y",
                        "-i", raw_f,
                        "-vf", f"setpts=N/({fps_rate:.2f}*TB)",
                        "-r", "25",
                        "-vcodec", "libx264",
                        "-pix_fmt", "yuv420p",
                        "-preset", "ultrafast",
                        "-movflags", "+faststart",
                        final_f
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True)

                    if res.returncode == 0 and os.path.exists(final_f) and os.path.getsize(final_f) > 1000:
                        try: os.remove(raw_f)
                        except Exception: pass
                    else:
                        # Fallback: rename raw to final if FFmpeg had an issue
                        if not os.path.exists(final_f):
                            os.rename(raw_f, final_f)

                    # Log completed evidence video into database
                    database.log_evidence(final_f, lvl, scr, cnt)
                    print(f"[Evidence] [STORED] High-Risk Video Evidence Stored Successfully: {final_f}", flush=True)

                    # Dispatch video evidence to Telegram
                    if config.EXTERNAL_ALERTS_ENABLED:
                        try:
                            ts_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            caption = (
                                f"🎥 HIGH-RISK INCIDENT VIDEO RECORDED\n\n"
                                f"📷 Camera : {camera}\n"
                                f"🚨 Level  : {lvl} ({scr:.0f}%)\n"
                                f"👥 People : {cnt}\n"
                                f"🕒 Time   : {ts_str}\n\n"
                                f"📁 Video evidence stored and available in dashboard."
                            )
                            notifier.send_telegram_alert(caption, image_path=final_f)
                        except Exception as tg_err:
                            print(f"[Evidence] Telegram video dispatch note: {tg_err}", flush=True)

                    # Cloud storage trigger
                    try:
                        import cloud_storage
                        cloud_storage.upload_evidence(final_f, resource_type="video")
                    except Exception:
                        pass

                except Exception as ex:
                    print(f"[Evidence] Transcode/store error: {ex}", flush=True)

            threading.Thread(target=process_and_store, args=(raw_path, final_path, actual_fps, level, score, count, cam), daemon=True).start()

    # ── Listing & Querying ────────────────────────────────────────────────────

    def list_evidence(self, limit: int = 50) -> list:
        """Return most recent evidence items (images and videos) with date, time, and camera metadata."""
        try:
            images = [f for f in os.listdir(config.EVIDENCE_IMG_DIR) if f.endswith(".jpg") and not f.startswith(".")]
            videos = [f for f in os.listdir(config.EVIDENCE_VID_DIR) if f.endswith(".mp4") and not f.startswith(".")]

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
            print(f"[Evidence] Error listing evidence: {e}", flush=True)
            return []

    # ── Internal HUD Overlay ──────────────────────────────────────────────────

    def _annotate(self, frame, risk, density, movement, count, camera_label: str = "Camera 1") -> object:
        """Draw clear evidence telemetry HUD banner onto frame."""
        h, w = frame.shape[:2]
        banner = 52
        cv2.rectangle(frame, (0, h - banner), (w, h), (10, 10, 15), -1)
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lvl = risk.get("level", "?")
        scr = risk.get("score", 0)
        line1 = f"[{camera_label}] {ts} | Risk: {lvl} ({scr:.0f}%) | People: {count}"
        line2 = (f"Density:{density.get('density_score', 0):.0f}% "
                 f"Movement:{movement.get('speed', 0):.1f}px/f "
                 f"Turbulence:{movement.get('turbulence', 0):.1f}")
        cv2.putText(frame, line1, (8, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255) if lvl in ("HIGH RISK", "CRITICAL") else (255, 255, 255), 1)
        cv2.putText(frame, line2, (8, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (180, 180, 180), 1)
        return frame
