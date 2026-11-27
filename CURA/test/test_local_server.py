import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import dev_services


class LocalServerTests(unittest.TestCase):
    def setUp(self):
        self.server = dev_services.ThreadingHTTPServer(
            ("127.0.0.1", 0), dev_services.FrontendOnlyHandler
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

    def test_render_token_is_read_from_ignored_local_secrets_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            secrets_path = root / "CURA" / "include" / "secrets.h"
            secrets_path.parent.mkdir(parents=True)
            secrets_path.write_text(
                '#define DEVICE_API_TOKEN "test-render-token"\n',
                encoding="utf-8",
            )
            with (
                patch.object(dev_services, "ROOT", root),
                patch.dict(dev_services.os.environ, {"RENDER_DEVICE_TOKEN": ""}),
            ):
                token = dev_services.render_device_token()

        self.assertEqual(token, "test-render-token")

    def test_root_redirects_to_dashboard_page(self):
        self.connection.request("GET", "/")
        response = self.connection.getresponse()
        response.read()
        self.assertEqual(response.status, 302)
        self.assertEqual(response.getheader("Location"), "/docs/pages/index.html")

    def test_alert_actions_are_proxied_to_the_api(self):
        response_body = json.dumps({"alert": {"id": 4, "status": "acknowledged"}})
        with patch.object(
            dev_services,
            "get_response",
            return_value=(200, response_body.encode("utf-8")),
        ) as proxy_request:
            self.connection.request("POST", "/api/v1/alerts/4/acknowledge")
            response = self.connection.getresponse()
            body = json.loads(response.read())

        self.assertEqual(response.status, 200)
        self.assertEqual(body["alert"]["status"], "acknowledged")
        args, kwargs = proxy_request.call_args
        self.assertEqual(
            args[0],
            f"{dev_services.API_BASE_URL}/api/v1/alerts/4/acknowledge",
        )
        self.assertEqual(kwargs["method"], "POST")
        self.assertEqual(kwargs["data"], b"")
        self.assertIn("X-Device-Token", kwargs["headers"])

    def test_wokwi_readings_are_forwarded_to_render_with_local_secret(self):
        payload = json.dumps({"heart_rate_bpm": 72}).encode("utf-8")
        response_body = json.dumps({"reading": {"id": 8}}).encode("utf-8")
        with (
            patch.object(dev_services, "RENDER_DEVICE_TOKEN", "render-secret"),
            patch.object(
                dev_services,
                "get_response",
                return_value=(201, response_body),
            ) as proxy_request,
        ):
            self.connection.request(
                "POST",
                "/api/v1/readings",
                payload,
                {
                    "Content-Type": "application/json",
                    "X-Device-Token": "dev-token",
                },
            )
            response = self.connection.getresponse()
            body = json.loads(response.read())

        self.assertEqual(response.status, 201)
        self.assertEqual(body["reading"]["id"], 8)
        args, kwargs = proxy_request.call_args
        self.assertEqual(args[0], dev_services.RENDER_API_URL)
        self.assertEqual(kwargs["method"], "POST")
        self.assertEqual(kwargs["data"], payload)
        self.assertEqual(
            kwargs["headers"]["X-Device-Token"],
            "render-secret",
        )
        self.assertEqual(kwargs["timeout"], 65)

    def test_wokwi_render_proxy_requires_local_header_and_render_secret(self):
        with (
            patch.object(dev_services, "RENDER_DEVICE_TOKEN", ""),
            patch.object(dev_services, "get_response") as proxy_request,
        ):
            self.connection.request(
                "POST",
                "/api/v1/readings",
                json.dumps({"heart_rate_bpm": 72}),
                {"Content-Type": "application/json"},
            )
            response = self.connection.getresponse()
            missing_header = json.loads(response.read())

            self.connection.request(
                "POST",
                "/api/v1/readings",
                json.dumps({"heart_rate_bpm": 72}),
                {
                    "Content-Type": "application/json",
                    "X-Device-Token": "dev-token",
                },
            )
            response = self.connection.getresponse()
            missing_secret = json.loads(response.read())

        self.assertEqual(response.status, 503)
        self.assertIn("DEVICE_API_TOKEN", missing_secret["error"])
        self.assertEqual(missing_header["error"], "token local invalido")
        proxy_request.assert_not_called()

    def test_api_outage_is_returned_as_service_unavailable(self):
        with patch.object(dev_services, "get_response", return_value=(None, b"")):
            self.connection.request("GET", "/api/v1/latest")
            response = self.connection.getresponse()
            body = json.loads(response.read())

        self.assertEqual(response.status, 503)
        self.assertEqual(body, {"error": "api indisponivel"})

    def test_dashboard_page_and_local_assets_are_served(self):
        self.connection.request("GET", "/docs/pages/index.html")
        response = self.connection.getresponse()
        body = response.read()
        self.assertEqual(response.status, 200)
        self.assertIn(b"<!doctype html>", body[:128].lower())
        self.assertIn(b'href="../assets/css/home.css"', body)
        self.assertIn(b'href="hardware.html"', body)

    def test_dashboard_pages_and_overview_links_are_available(self):
        for page in (
            "hardware",
            "firmware",
            "docs",
            "workbench",
            "medications",
            "login",
            "profile",
        ):
            with self.subTest(page=page):
                self.connection.request("GET", f"/docs/pages/{page}.html")
                response = self.connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn(b'href="index.html"', body)

    def test_account_controls_are_available_on_all_pages(self):
        for page in (
            "index",
            "hardware",
            "firmware",
            "docs",
            "workbench",
            "medications",
            "login",
            "profile",
        ):
            with self.subTest(page=page):
                self.connection.request("GET", f"/docs/pages/{page}.html")
                response = self.connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn(b'data-account-link', body)
                self.assertIn(b'data-welcome-user', body)
                self.assertIn(b'data-auth-action', body)
                self.assertIn(b'aria-label="Meu perfil"', body)

    def test_index_resources_and_navigation_resolve(self):
        site_base = "https://example.github.io/tinkercad/docs/pages/"
        for relative_path in (
            "../assets/css/home.css",
            "../assets/js/api.js",
            "../assets/js/home.js",
            "../assets/js/care-features.js",
            "hardware.html",
            "firmware.html",
            "docs.html",
            "workbench.html",
            "medications.html",
            "login.html",
            "profile.html",
            "index.html",
        ):
            with self.subTest(relative_path=relative_path):
                resolved_path = urlsplit(urljoin(site_base, relative_path)).path
                self.assertTrue(resolved_path.startswith("/tinkercad/docs/"))

        for path in (
            "/docs/assets/css/home.css",
            "/docs/assets/js/home.js",
            "/docs/assets/js/api.js",
            "/docs/assets/js/care-features.js",
            "/docs/pages/index.html",
            "/docs/pages/hardware.html",
            "/docs/pages/firmware.html",
            "/docs/pages/docs.html",
            "/docs/pages/workbench.html",
            "/docs/pages/medications.html",
            "/docs/pages/login.html",
            "/docs/pages/profile.html",
        ):
            with self.subTest(path=path):
                self.connection.request("GET", path)
                response = self.connection.getresponse()
                response.read()
                self.assertEqual(response.status, 200)

    def test_section_pages_link_back_to_site_root(self):
        site_base = "https://example.github.io/tinkercad/docs/pages/"
        for page in ("hardware", "firmware", "docs", "workbench"):
            with self.subTest(page=page):
                self.connection.request("GET", f"/docs/pages/{page}.html")
                response = self.connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn(b'href="index.html"', body)
                self.assertEqual(
                    urlsplit(urljoin(site_base, "index.html")).path,
                    "/tinkercad/docs/pages/index.html",
                )
