"""
crowd_count.py — Vision Guard Crowd Counting Module
Tracks person count history and computes session statistics.
"""

from collections import deque


class CrowdCounter:
    """Tracks crowd size over a session."""

    def __init__(self, history_size: int = 300):
        self._history   = deque(maxlen=history_size)
        self._current   = 0
        self._session_max   = 0
        self._session_min   = None
        self._frame_total   = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def update(self, count: int):
        """Record a new count observation."""
        self._current  = count
        self._frame_total += 1
        self._history.append(count)

        if count > self._session_max:
            self._session_max = count
        if self._session_min is None or count < self._session_min:
            self._session_min = count

    @property
    def current(self) -> int:
        return self._current

    @property
    def session_max(self) -> int:
        return self._session_max

    @property
    def session_min(self) -> int:
        return self._session_min if self._session_min is not None else 0

    @property
    def session_avg(self) -> float:
        if not self._history:
            return 0.0
        return round(sum(self._history) / len(self._history), 1)

    @property
    def history(self) -> list:
        return list(self._history)

    @property
    def frame_total(self) -> int:
        return self._frame_total

    def reset(self):
        """Reset all counters for a new session."""
        self._history.clear()
        self._current     = 0
        self._session_max = 0
        self._session_min = None
        self._frame_total = 0

    def summary(self) -> dict:
        return {
            "current":     self.current,
            "session_max": self.session_max,
            "session_min": self.session_min,
            "session_avg": self.session_avg,
            "frames":      self.frame_total,
        }
