"""circuitbreaker.py：熔断器（基线：只计数，不熔断）。"""
from __future__ import annotations


class Breaker:
    def __init__(self, window: int = 4, threshold: int = 2, min_samples: int = 2,
                 open_ticks: int = 3, probes: int = 1):
        self.window = window
        self.threshold = threshold
        self.min_samples = min_samples
        self.open_ticks = open_ticks
        self.probes = probes
        self.results = []
        self.state = "CLOSED"
        self.opened_at = None
        self.rejected = 0
        self.probe_count = 0
        self.allowed = 0

    def call(self, ok: bool, at: int) -> dict:
        """基线：永远放行，状态永远 CLOSED。"""
        self.results.append({"ok": ok, "at": at})
        self.allowed += 1
        return {"allowed": True, "state": self.state}

    def tick(self, now: int) -> dict:
        raise NotImplementedError("状态迁移还没实现")

    def persist(self) -> bytes:
        raise NotImplementedError("快照还没实现")

    def restore(self, blob: bytes = None) -> dict:
        raise NotImplementedError("重启恢复还没实现")

    def stats(self) -> dict:
        return {"state": self.state, "rejected": self.rejected, "allowed": self.allowed,
                "probe_count": self.probe_count, "window": self.window,
                "threshold": self.threshold, "min_samples": self.min_samples,
                "open_ticks": self.open_ticks, "probes": self.probes}
