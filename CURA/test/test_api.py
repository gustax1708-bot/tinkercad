import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

import api


class ApiHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_database = api.DATABASE
        self.original_token = api.DEVICE_TOKEN
        api.DATABASE = Path(self.temp_dir.name) / "readings.sqlite3"
        api.DEVICE_TOKEN = "test-token"
        self.server = api.ThreadingHTTPServer(("127.0.0.1", 0), api.ApiHandler)
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
        api.DATABASE = self.original_database
        api.DEVICE_TOKEN = self.original_token
        self.temp_dir.cleanup()

    def post_reading(self, payload, token="test-token"):
        self.connection.request(
            "POST",
            "/api/v1/readings",
            json.dumps(payload),
            {
                "Content-Type": "application/json",
                "X-Device-Token": token,
            },
        )
        response = self.connection.getresponse()
        return response.status, json.loads(response.read())

    def test_api_root_redirects_to_frontend(self):
        self.connection.request("GET", "/")
        response = self.connection.getresponse()
        response.read()
        self.assertEqual(response.status, 302)
        self.assertEqual(response.getheader("Location"), api.SITE_URL)

    def test_telemetry_endpoints_are_not_cached(self):
        for path in ("/api/v1/latest", "/api/v1/history"):
            self.connection.request("GET", path)
            response = self.connection.getresponse()
            response.read()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Cache-Control"), "no-store")

    def test_manual_panic_is_saved_and_remains_visible(self):
        panic = {
            "device_id": "pulseira-01",
            "spo2_percent": 97,
            "heart_rate_bpm": 72,
            "temperature_c": 36.5,
            "panic": True,
            "sensor_contact": True,
        }
        status, _ = self.post_reading(panic)
        self.assertEqual(status, 201)

        routine = {**panic, "panic": False, "heart_rate_bpm": 74}
        status, _ = self.post_reading(routine)
        self.assertEqual(status, 201)

        self.connection.request("GET", "/api/v1/latest")
        response = self.connection.getresponse()
        result = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertFalse(result["reading"]["panic"])
        self.assertTrue(result["latest_panic"]["panic"])
        self.assertEqual(result["latest_panic"]["heart_rate_bpm"], 72)

    def test_latest_valid_reading_is_kept_when_panic_is_logged(self):
        normal = {
            "device_id": "pulseira-01",
            "spo2_percent": 97,
            "heart_rate_bpm": 72,
            "temperature_c": 36.5,
            "panic": False,
            "sensor_contact": True,
        }
        self.assertEqual(self.post_reading(normal)[0], 201)

        panic = {**normal, "panic": True, "sensor_contact": False}
        self.assertEqual(self.post_reading(panic)[0], 201)

        self.connection.request("GET", "/api/v1/latest")
        response = self.connection.getresponse()
        result = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertFalse(result["reading"]["panic"])
        self.assertTrue(result["latest_panic"]["panic"])
        self.assertEqual(result["reading"]["heart_rate_bpm"], 72)
        self.assertEqual(result["reading"]["spo2_percent"], 97)

    def test_abnormal_values_do_not_create_panic(self):
        status, result = self.post_reading(
            {
                "spo2_percent": 80,
                "heart_rate_bpm": 150,
                "panic": False,
                "sensor_contact": True,
            }
        )
        self.assertEqual(status, 201)
        self.assertFalse(result["reading"]["panic"])
        self.assertEqual(result["reading"]["status"], "normal_demo")

    def test_invalid_readings_and_tokens_are_rejected(self):
        status, _ = self.post_reading({"spo2_percent": 120})
        self.assertEqual(status, 400)
        status, _ = self.post_reading({"panic": True}, token="wrong")
        self.assertEqual(status, 401)

    def test_temperature_trend_is_interpreted(self):
        self.assertEqual(self.post_reading({"temperature_c": 36.0})[0], 201)
        status, result = self.post_reading({"temperature_c": 36.5})
        self.assertEqual(status, 201)
        self.assertEqual(result["reading"]["temperature_trend"], "subindo")


if __name__ == "__main__":
    unittest.main()
