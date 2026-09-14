"""Clock offset calibration for SwitchBot locks (pure logic)."""

from __future__ import annotations

from collections import deque
from statistics import median
from typing import Final

MAX_SAMPLES: Final = 5
MIN_VALID: Final = 0
MAX_VALID: Final = 3600

class ClockOffsetTracker:
    """Median drift of a lock's RTC vs real time, from push-triggered fetches."""

    def __init__(self, samples: list[int] | None = None) -> None:
        self._samples: deque[int] = deque(samples or [], maxlen=MAX_SAMPLES)

    @property
    def samples(self) -> list[int]:
        return list(self._samples)

    def add_sample(self, fetch_time: float, newest_log_ts: float) -> bool:
        """Record fetch_time - newest_log_ts when plausible; True if stored."""
        sample = int(fetch_time - newest_log_ts)
        if not MIN_VALID < sample <= MAX_VALID:
            return False
        self._samples.append(sample)
        return True

    def offset(self) -> int | None:
        return int(median(self._samples)) if self._samples else None
