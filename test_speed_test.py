"""Checks for the download speed script using a local HTTP server."""

import contextlib
import io
import subprocess
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import speed_test

SCRIPT = Path(__file__).with_name("speed_test.py")
PAYLOAD = b"x" * 150_000  # Larger than the script's read chunk.


class TestServerHandler(BaseHTTPRequestHandler):
    request_count = 0
    active = 0
    max_active = 0
    lock = threading.Lock()

    def do_GET(self):
        handler = type(self)
        with handler.lock:
            handler.request_count += 1
            handler.active += 1
            handler.max_active = max(handler.max_active, handler.active)
        try:
            if self.path == "/error":
                self.send_error(503)
                return
            time.sleep(0.01)  # Make overlapping requests visible to the test.
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD)))
            self.end_headers()
            self.wfile.write(PAYLOAD)
        finally:
            with handler.lock:
                handler.active -= 1

    def log_message(self, format, *args):
        pass


class SpeedTestChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), TestServerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        TestServerHandler.request_count = 0
        TestServerHandler.active = 0
        TestServerHandler.max_active = 0

    def run_script(self, address):
        return subprocess.run(
            [sys.executable, str(SCRIPT), address],
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_ten_complete_downloads(self):
        result = self.run_script(self.url + "/file")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(TestServerHandler.request_count, 10)
        self.assertEqual(TestServerHandler.max_active, 1)
        self.assertIn("Total downloaded: 1,500,000 bytes", result.stdout)
        self.assertIn("Average download speed:", result.stdout)

    def test_http_failure_stops_without_average(self):
        result = self.run_script(self.url + "/error")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(TestServerHandler.request_count, 1)
        self.assertIn("Error on request 1", result.stdout)
        self.assertNotIn("Average download speed:", result.stdout)

    def test_invalid_address_is_rejected(self):
        result = self.run_script("not-a-url")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("provide a full HTTP or HTTPS URL", result.stderr)
        self.assertEqual(TestServerHandler.request_count, 0)

    def test_speed_calculation(self):
        output = io.StringIO()
        # Ten responses of 150,000 bytes, each taking 2 seconds, equal 0.60 Mbit/s.
        with patch.object(speed_test, "download_once", return_value=(150_000, 2.0)), \
             patch.object(sys, "argv", ["speed_test.py", self.url]), \
             contextlib.redirect_stdout(output):
            self.assertEqual(speed_test.main(), 0)
        self.assertIn("Average request time: 2.000 s", output.getvalue())
        self.assertIn("Average download speed: 0.60 Mbit/s", output.getvalue())


if __name__ == "__main__":
    unittest.main()
