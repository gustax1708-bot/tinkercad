import http.client
import sys
import threading
import unittest
from pathlib import Path
from urllib.parse import urljoin, urlsplit


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

    def test_root_redirects_to_dashboard_page(self):
        self.connection.request("GET", "/")
        response = self.connection.getresponse()
        response.read()
        self.assertEqual(response.status, 302)
        self.assertEqual(response.getheader("Location"), "/docs/pages/index.html")

    def test_dashboard_page_and_local_assets_are_served(self):
        self.connection.request("GET", "/docs/pages/index.html")
        response = self.connection.getresponse()
        body = response.read()
        self.assertEqual(response.status, 200)
        self.assertIn(b"<!doctype html>", body[:128].lower())
        self.assertIn(b'href="../assets/css/home.css"', body)
        self.assertIn(b'href="hardware.html"', body)

    def test_dashboard_pages_and_overview_links_are_available(self):
        for page in ("hardware", "firmware", "docs", "workbench"):
            with self.subTest(page=page):
                self.connection.request("GET", f"/docs/pages/{page}.html")
                response = self.connection.getresponse()
                body = response.read()
                self.assertEqual(response.status, 200)
                self.assertIn(b'href="index.html"', body)

    def test_index_resources_and_navigation_resolve(self):
        site_base = "https://example.github.io/tinkercad/docs/pages/"
        for relative_path in (
            "../assets/css/home.css",
            "../assets/js/api.js",
            "../assets/js/home.js",
            "hardware.html",
            "firmware.html",
            "docs.html",
            "workbench.html",
            "index.html",
        ):
            with self.subTest(relative_path=relative_path):
                resolved_path = urlsplit(urljoin(site_base, relative_path)).path
                self.assertTrue(resolved_path.startswith("/tinkercad/docs/"))

        for path in (
            "/docs/assets/css/home.css",
            "/docs/assets/js/home.js",
            "/docs/assets/js/api.js",
            "/docs/pages/index.html",
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
