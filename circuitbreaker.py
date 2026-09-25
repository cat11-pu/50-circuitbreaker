"""circuitbreaker.py：熔断器（滑动窗口判定 + 三态状态机 + 快照恢复）。"""
from __future__ import annotations

import json
import os
from collections import deque

SNAPSHOT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "breaker_snapshot.json")


class Breaker:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

    def __init__(self, window: int = 4, threshold: int = 2, min_samples: int = 2,
                 open_ticks: int = 3, probes: int = 1):
        self.window = window
        self.threshold = threshold
        self.min_samples = min_samples
        self.open_ticks = open_ticks
        self.probes = probes
        self.results = deque(maxlen=window)
        self.state = self.CLOSED
        self.opened_at = None
        self.rejected = 0
        self.probe_count = 0
        self.allowed = 0
        self._snapshot = None

    def call(self, ok: bool, at: int) -> dict:
        """记录一次请求结果，返回是否放行与当前状态。"""
        if self.state == self.OPEN:
            self.rejected += 1
            return {"allowed": False, "state": self.state}
        if self.state == self.HALF_OPEN:
            if self.probe_count >= self.probes:
                self.rejected += 1
                return {"allowed": False, "state": self.state}
            self.probe_count += 1
            self.allowed += 1
            self.results.append({"ok": ok, "at": at})
            if not ok:
                self._open(at)
            elif self.probe_count >= self.probes:
                self.state = self.CLOSED
                self.results.clear()
            return {"allowed": True, "state": self.state}
        self.allowed += 1
        self.results.append({"ok": ok, "at": at})
        failures = sum(1 for r in self.results if not r["ok"])
        if len(self.results) >= self.min_samples and failures >= self.threshold:
            self._open(at)
        return {"allowed": True, "state": self.state}

    def _open(self, at: int) -> None:
        self.state = self.OPEN
        self.opened_at = at
        self.results.clear()

    def tick(self, now: int) -> dict:
        """推进状态：OPEN 持续至少 open_ticks 后转 HALF_OPEN。"""
        if self.state == self.OPEN and self.opened_at is not None \
                and now - self.opened_at >= self.open_ticks:
            self.state = self.HALF_OPEN
            self.probe_count = 0
        return {"state": self.state}

    def persist(self) -> bytes:
        """把状态、计数与窗口内容落盘，并返回快照字节。"""
        blob = json.dumps({
            "window": self.window, "threshold": self.threshold,
            "min_samples": self.min_samples, "open_ticks": self.open_ticks,
            "probes": self.probes, "state": self.state,
            "opened_at": self.opened_at, "rejected": self.rejected,
            "probe_count": self.probe_count, "allowed": self.allowed,
            "results": list(self.results),
        }).encode()
        with open(SNAPSHOT_PATH, "wb") as fh:
            fh.write(blob)
        self._snapshot = blob
        return blob

    def restore(self, blob: bytes = None) -> dict:
        """从快照恢复；blob 缺省时依次取内存快照、磁盘快照，都没有则保持现状。"""
        if blob is None:
            blob = self._snapshot
        if blob is None and os.path.exists(SNAPSHOT_PATH):
            with open(SNAPSHOT_PATH, "rb") as fh:
                blob = fh.read()
        if blob is None:
            return self.stats()
        data = json.loads(blob.decode("utf-8") if isinstance(blob, bytes) else blob)
        self.window = data["window"]
        self.threshold = data["threshold"]
        self.min_samples = data["min_samples"]
        self.open_ticks = data["open_ticks"]
        self.probes = data["probes"]
        self.state = data["state"]
        self.opened_at = data["opened_at"]
        self.rejected = data["rejected"]
        self.probe_count = data["probe_count"]
        self.allowed = data["allowed"]
        self.results = deque(data["results"], maxlen=self.window)
        return self.stats()

    def stats(self) -> dict:
        return {"state": self.state, "rejected": self.rejected, "allowed": self.allowed,
                "probe_count": self.probe_count, "window": self.window,
                "threshold": self.threshold, "min_samples": self.min_samples,
                "open_ticks": self.open_ticks, "probes": self.probes}
