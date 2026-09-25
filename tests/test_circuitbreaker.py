import json
import os
import threading
import unittest
import urllib.error
import urllib.request

import circuitbreaker
from circuitbreaker import Breaker
from server import serve

class TestBreaker(unittest.TestCase):
    def test_first_call_allowed(self):
        self.assertTrue(Breaker().call(True, 0)["allowed"])

    def test_state_starts_closed(self):
        self.assertEqual(Breaker().stats()["state"], "CLOSED")

    def test_results_recorded(self):
        breaker = Breaker()
        breaker.call(True, 0)
        self.assertEqual(len(breaker.results), 1)

    def test_stats_shape(self):
        self.assertIn("threshold", Breaker().stats())

    def test_http_call(self):
        server = serve(0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
        with urllib.request.urlopen(base + "/call", data=b'{"ok": false, "at": 0}', timeout=5) as response:
            self.assertEqual(json.loads(response.read())["state"], "CLOSED")
        server.shutdown()

    def test_opens_after_threshold_failures(self):
        breaker = Breaker()
        breaker.call(False, 0)
        result = breaker.call(False, 1)
        self.assertEqual(result["state"], "OPEN")
        self.assertEqual(breaker.opened_at, 1)

    def test_open_rejects_and_counts(self):
        breaker = Breaker()
        breaker.call(False, 0)
        breaker.call(False, 1)
        result = breaker.call(True, 2)
        self.assertFalse(result["allowed"])
        self.assertEqual(breaker.rejected, 1)
        self.assertEqual(breaker.allowed, 2)

    def test_tick_half_open_after_open_ticks(self):
        breaker = Breaker()
        breaker.call(False, 0)
        breaker.call(False, 1)
        self.assertEqual(breaker.tick(3)["state"], "OPEN")
        self.assertEqual(breaker.tick(4)["state"], "HALF_OPEN")
        self.assertEqual(breaker.probe_count, 0)

    def test_probe_success_closes_and_clears_window(self):
        breaker = Breaker()
        breaker.call(False, 0)
        breaker.call(False, 1)
        breaker.tick(4)
        self.assertEqual(breaker.call(True, 5)["state"], "CLOSED")
        self.assertEqual(len(breaker.results), 0)
        breaker.call(True, 6)
        breaker.call(False, 7)
        self.assertEqual(breaker.state, "CLOSED")

    def test_probe_failure_reopens_and_retires(self):
        breaker = Breaker()
        breaker.call(False, 0)
        breaker.call(False, 1)
        breaker.tick(4)
        self.assertEqual(breaker.call(False, 5)["state"], "OPEN")
        self.assertEqual(breaker.opened_at, 5)
        self.assertEqual(breaker.tick(7)["state"], "OPEN")
        self.assertEqual(breaker.tick(8)["state"], "HALF_OPEN")

    def test_window_is_bounded(self):
        breaker = Breaker(window=4, threshold=100, min_samples=2)
        for at in range(100000):
            breaker.call(True, at)
        self.assertEqual(len(breaker.results), 4)
        self.assertEqual(breaker.allowed, 100000)

    def test_persist_restore_roundtrip(self):
        breaker = Breaker()
        breaker.call(True, 0)
        breaker.call(False, 1)
        blob = breaker.persist()
        try:
            restored = Breaker()
            restored.restore(blob)
            self.assertEqual(restored.stats(), breaker.stats())
            self.assertEqual(list(restored.results), list(breaker.results))
        finally:
            if os.path.exists(circuitbreaker.SNAPSHOT_PATH):
                os.remove(circuitbreaker.SNAPSHOT_PATH)
