import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import render_server


class RenderServerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = render_server.api.DATABASE
        self.original_token = render_server.api.DEVICE_TOKEN
        render_server.api.DATABASE = Path(self.temp_dir.name) / "readings.sqlite3"
        render_server.api.DEVICE_TOKEN = "test-token"
        self.server = render_server.ThreadingHTTPServer(
            ("127.0.0.1", 0), render_server.RenderHandler
        )
        self.server_thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.server_thread.start()
        self.connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port
        )

    def tearDown(self):
        self.connection.close()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=2)
        render_server.api.DATABASE = self.original_database
        render_server.api.DEVICE_TOKEN = self.original_token
        self.temp_dir.cleanup()

    def test_root_serves_dashboard(self):
        self.connection.request("GET", "/")
        response = self.connection.getresponse()
        body = response.read()
        self.assertEqual(response.status, 200)
        self.assertIn(b"<!doctype html>", body[:128].lower())
        self.assertIn(b'/docs/assets/css/home.css', body)

    def test_dashboard_can_read_demo_telemetry(self):
        self.connection.request("GET", "/api/v1/latest")
        response = self.connection.getresponse()
        body = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertIsNone(body["reading"])

    def test_dashboard_pages_and_overview_links_are_available(self):
        for page in ("hardware", "firmware", "docs", "workbench"):
            with self.subTest(page=page):
                self.connection.request("GET", f"/docs/pages/{page}.html")
                response = self.connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn(b'href="/"', body)

    def test_index_resources_and_navigation_resolve(self):
        for path in (
            "/docs/assets/css/home.css",
            "/docs/assets/js/home.js",
            "/docs/assets/js/api.js",
            "/docs/pages/hardware.html",
            "/docs/pages/firmware.html",
            "/docs/pages/docs.html",
            "/docs/pages/workbench.html",
        ):
            with self.subTest(path=path):
                self.connection.request("GET", path)
                response = self.connection.getresponse()
                response.read()
                self.assertEqual(response.status, 200)

    def test_telemetry_writes_still_require_device_token(self):
        payload = json.dumps({"spo2_percent": 97, "sensor_contact": True})
        self.connection.request(
            "POST",
            "/api/v1/readings",
            payload,
            {"Content-Type": "application/json"},
        )
        response = self.connection.getresponse()
        response.read()
        self.assertEqual(response.status, 401)

        self.connection.request(
            "POST",
            "/api/v1/readings",
            payload,
            {
                "Content-Type": "application/json",
                "X-Device-Token": "test-token",
            },
        )
        response = self.connection.getresponse()
        response.read()
        self.assertEqual(response.status, 201)
