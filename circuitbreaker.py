"""circuitbreaker.py：熔断器（CLOSED / OPEN / HALF_OPEN 状态机）。"""
from __future__ import annotations

import json
import os
from collections import deque

SNAPSHOT_PATH = "breaker_snapshot.json"


class Breaker:
    def __init__(self, window: int = 4, threshold: int = 2, min_samples: int = 2,
                 open_ticks: int = 3, probes: int = 1):
        self.window = window
        self.threshold = threshold
        self.min_samples = min_samples
        self.open_ticks = open_ticks
        self.probes = probes
        # 只保留最近 window 次放行结果，不保留全部历史。
        self.results = deque(maxlen=window)
        self.state = "CLOSED"
        self.opened_at = None
        self.rejected = 0
        self.probe_count = 0
        self.allowed = 0

    def call(self, ok: bool, at: int) -> dict:
        if self.state == "OPEN":
            # 不变量：OPEN 期间不放行任何普通请求。
            self.rejected += 1
            return {"allowed": False, "state": self.state}
        if self.state == "HALF_OPEN":
            if self.probe_count >= self.probes:
                self.rejected += 1
                return {"allowed": False, "state": self.state}
            self.probe_count += 1
            self.allowed += 1
            if not ok:
                self._open(at)
            elif self.probe_count >= self.probes:
                self._close()
            return {"allowed": True, "state": self.state}
        # CLOSED：放行并计入滑动窗口。
        self.results.append({"ok": ok, "at": at})
        self.allowed += 1
        if len(self.results) >= self.min_samples and self._failures() >= self.threshold:
            self._open(at)
        return {"allowed": True, "state": self.state}

    def tick(self, now: int) -> dict:
        if self.state == "OPEN" and self.opened_at is not None \
                and now - self.opened_at >= self.open_ticks:
            self.state = "HALF_OPEN"
            self.probe_count = 0
        return {"state": self.state}

    def persist(self) -> bytes:
        blob = json.dumps({
            "state": self.state,
            "opened_at": self.opened_at,
            "rejected": self.rejected,
            "allowed": self.allowed,
            "probe_count": self.probe_count,
            "results": list(self.results),
        }).encode()
        with open(SNAPSHOT_PATH, "wb") as fh:
            fh.write(blob)
        return blob

    def restore(self, blob: bytes = None) -> dict:
        if blob is None:
            if not os.path.exists(SNAPSHOT_PATH):
                return self.stats()
            with open(SNAPSHOT_PATH, "rb") as fh:
                blob = fh.read()
        data = json.loads(blob)
        self.state = data["state"]
        self.opened_at = data["opened_at"]
        self.rejected = data["rejected"]
        self.allowed = data["allowed"]
        self.probe_count = data["probe_count"]
        self.results = deque(data["results"], maxlen=self.window)
        return self.stats()

    def stats(self) -> dict:
        return {"state": self.state, "rejected": self.rejected, "allowed": self.allowed,
                "probe_count": self.probe_count, "window": self.window,
                "threshold": self.threshold, "min_samples": self.min_samples,
                "open_ticks": self.open_ticks, "probes": self.probes}

    def _failures(self) -> int:
        return sum(1 for r in self.results if not r["ok"])

    def _open(self, at: int) -> None:
        self.state = "OPEN"
        self.opened_at = at
        self.results.clear()

    def _close(self) -> None:
        self.state = "CLOSED"
        self.opened_at = None
        self.results.clear()
