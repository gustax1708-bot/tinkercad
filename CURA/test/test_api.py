import http.client
from contextlib import redirect_stdout
from io import StringIO
import json
import sqlite3
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
            self.connection.request(
                "GET", path, headers={"X-Device-Token": "test-token"}
            )
            response = self.connection.getresponse()
            response.read()
            self.assertEqual(response.status, 200)
            self.assertEqual(response.getheader("Cache-Control"), "no-store")
            self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
            self.assertEqual(response.getheader("X-Frame-Options"), "DENY")

    def test_cors_only_allows_configured_dashboard_origin(self):
        for origin, expected in (
            ("http://localhost:8080", "http://localhost:8080"),
            ("https://attacker.example", None),
        ):
            self.connection.request(
                "OPTIONS",
                "/api/v1/latest",
                headers={"Origin": origin},
            )
            response = self.connection.getresponse()
            response.read()
            self.assertEqual(response.status, 204)
            self.assertEqual(
                response.getheader("Access-Control-Allow-Origin"), expected
            )

    def test_telemetry_reads_require_device_token(self):
        for path in ("/api/v1/latest", "/api/v1/history"):
            self.connection.request("GET", path)
            response = self.connection.getresponse()
            response.read()
            self.assertEqual(response.status, 401)

            self.connection.request(
                "GET", path, headers={"X-Device-Token": "test-token"}
            )
            response = self.connection.getresponse()
            response.read()
            self.assertEqual(response.status, 200)

    def test_api_log_does_not_include_biometric_values(self):
        output = StringIO()
        payload = {
            "spo2_percent": 97,
            "heart_rate_bpm": 72,
            "temperature_c": 36.5,
            "sensor_contact": True,
        }
        with redirect_stdout(output):
            status, _ = self.post_reading(payload)

        self.assertEqual(status, 201)
        log = output.getvalue()
        self.assertIn("Telemetria armazenada", log)
        for sensitive_value in ("SpO2", "pulso", "temperatura", "97.0", "72.0", "36.5"):
            self.assertNotIn(sensitive_value, log)

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

        self.connection.request(
            "GET", "/api/v1/latest", headers={"X-Device-Token": "test-token"}
        )
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

        self.connection.request(
            "GET", "/api/v1/latest", headers={"X-Device-Token": "test-token"}
        )
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

    def test_api_rejects_public_bind_with_development_token(self):
        original_host = api.HOST
        original_token = api.DEVICE_TOKEN
        try:
            api.HOST = "0.0.0.0"
            api.DEVICE_TOKEN = "dev-token"
            with self.assertRaises(ValueError):
                api.validate_security_configuration()
            api.DEVICE_TOKEN = "custom-random-token"
            api.validate_security_configuration()
        finally:
            api.HOST = original_host
            api.DEVICE_TOKEN = original_token

    def test_new_sensor_values_are_range_checked(self):
        for payload in (
            {"battery_percent": 101},
            {"battery_voltage": 5.1},
            {"acceleration_g": 33},
        ):
            with self.subTest(payload=payload):
                self.assertEqual(self.post_reading(payload)[0], 400)

    def test_temperature_trend_is_interpreted(self):
        self.assertEqual(self.post_reading({"temperature_c": 36.0})[0], 201)
        status, result = self.post_reading({"temperature_c": 36.5})
        self.assertEqual(status, 201)
        self.assertEqual(result["reading"]["temperature_trend"], "subindo")

    def test_new_sensor_fields_migrate_and_persist(self):
        connection = sqlite3.connect(api.DATABASE)
        try:
            connection.execute(
                """CREATE TABLE readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    spo2_percent REAL,
                    heart_rate_bpm REAL,
                    temperature_c REAL,
                    panic INTEGER NOT NULL,
                    sensor_contact INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    temperature_trend TEXT NOT NULL
                )"""
            )
            connection.execute(
                """INSERT INTO readings (
                    device_id, received_at, spo2_percent, heart_rate_bpm,
                    temperature_c, panic, sensor_contact, status,
                    temperature_trend
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "pulseira-01", "2026-01-01T00:00:00+00:00", 96.0,
                    70.0, 36.5, 0, 1, "normal_demo", "estavel",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        status, result = self.post_reading(
            {
                "spo2_percent": 98,
                "heart_rate_bpm": 72,
                "temperature_c": 36.8,
                "battery_percent": 84,
                "battery_voltage": 3.91,
                "acceleration_g": 1.02,
                "motion_active": True,
                "fall_detected": True,
                "sensor_contact": True,
            }
        )

        self.assertEqual(status, 201)
        reading = result["reading"]
        self.assertEqual(reading["battery_percent"], 84.0)
        self.assertEqual(reading["battery_voltage"], 3.91)
        self.assertEqual(reading["acceleration_g"], 1.02)
        self.assertTrue(reading["motion_active"])
        self.assertTrue(reading["fall_detected"])
        self.assertEqual(reading["status"], "queda_possivel")

        self.connection.request(
            "GET", "/api/v1/history", headers={"X-Device-Token": "test-token"}
        )
        response = self.connection.getresponse()
        history = json.loads(response.read())
        self.assertEqual(response.status, 200)
        self.assertEqual(len(history["readings"]), 2)
        self.assertEqual(history["readings"][1]["spo2_percent"], 96.0)


if __name__ == "__main__":
    unittest.main()
