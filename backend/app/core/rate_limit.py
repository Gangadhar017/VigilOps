"""Small in-process sliding-window rate limiter.

The backend runs as a single process (one Uvicorn worker), so an in-memory
limiter is sufficient and avoids introducing Redis.  State is lost on restart,
which only ever makes the limiter more permissive for one window.

Memory is bounded: keys whose window has emptied are removed, and a periodic
sweep drops expired keys, so attacker-chosen keys (for example made-up e-mail
addresses on the login form) cannot grow the table without limit.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, Tuple

_SWEEP_EVERY = 500      # operations between sweeps
_MAX_KEYS = 20_000      # hard cap; reaching it triggers an immediate sweep


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()
        self._operations = 0

    # All helpers below are called with the lock held.
    def _prune(self, key: str, now: float) -> Deque[float]:
        events = self._events.get(key)
        if events is None:
            return deque()
        cutoff = now - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if not events:
            del self._events[key]
        return events

    def _maybe_sweep(self, now: float) -> None:
        self._operations += 1
        if self._operations < _SWEEP_EVERY and len(self._events) < _MAX_KEYS:
            return
        self._operations = 0
        cutoff = now - self.window_seconds
        for key in [k for k, events in self._events.items() if not events or events[-1] <= cutoff]:
            del self._events[key]
        if len(self._events) >= _MAX_KEYS:
            # Still full of live keys: drop the least recently active half.
            oldest = sorted(self._events, key=lambda k: self._events[k][-1])[: _MAX_KEYS // 2]
            for key in oldest:
                del self._events[key]

    def _retry_after(self, events: Deque[float], now: float) -> int:
        return max(int(events[0] + self.window_seconds - now) + 1, 1)

    # -- public API ------------------------------------------------------
    def check(self, key: str) -> Tuple[bool, int]:
        """Return (allowed, retry_after_seconds) without recording an event."""
        now = time.monotonic()
        with self._lock:
            self._maybe_sweep(now)
            events = self._prune(key, now)
            if len(events) < self.max_events:
                return True, 0
            return False, self._retry_after(events, now)

    def hit(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            self._maybe_sweep(now)
            self._prune(key, now)
            self._events.setdefault(key, deque()).append(now)

    def allow(self, key: str) -> Tuple[bool, int]:
        """Check and, when allowed, record an event atomically."""
        now = time.monotonic()
        with self._lock:
            self._maybe_sweep(now)
            events = self._prune(key, now)
            if len(events) >= self.max_events:
                return False, self._retry_after(events, now)
            self._events.setdefault(key, deque()).append(now)
            return True, 0

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def tracked_keys(self) -> int:
        with self._lock:
            return len(self._events)
