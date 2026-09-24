import json
import threading
import unittest
import urllib.error
import urllib.request

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
