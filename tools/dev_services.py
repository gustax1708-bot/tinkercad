import argparse
import functools
import json
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
API_PORT = int(os.getenv("API_PORT", "8000"))
SITE_PORT = int(os.getenv("SITE_PORT", "8080"))
API_BASE_URL = f"http://127.0.0.1:{API_PORT}"
API_URL = f"{API_BASE_URL}/api/v1/latest"
API_HEALTH_URL = f"{API_BASE_URL}/api/v1/health"
API_HISTORY_URL = f"{API_BASE_URL}/api/v1/history"
SITE_URL = f"http://127.0.0.1:{SITE_PORT}/"
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "dev-token")


def get_response(url, headers=None, data=None, method=None):
    try:
        request = Request(url, data=data, headers=headers or {}, method=method)
        with urlopen(request, timeout=1) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()
    except URLError:
        return None, b""


def api_is_running():
    headers = {"X-Device-Token": DEVICE_TOKEN}
    for url, expected_keys in (
        (API_HEALTH_URL, {"status", "database"}),
        (API_URL, {"reading", "latest_panic", "active_alerts"}),
        (API_HISTORY_URL, {"readings"}),
    ):
        status, body = get_response(url, headers=headers)
        if status != 200:
            return False
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return False
        if not expected_keys.issubset(payload):
            return False
    return True


def site_is_running():
    status, body = get_response(SITE_URL)
    if status != 200 or b"<!doctype html>" not in body[:128].lower():
        return False

    for path in ("/CURA/readings.sqlite3", "/.git/config"):
        status, _ = get_response(f"{SITE_URL.rstrip('/')}{path}")
        if status not in (403, 404):
            return False

    for path in (
        "docs/pages/index.html",
        "docs/pages/docs.html",
        "docs/assets/js/api.js",
        "docs/assets/css/home.css",
    ):
        status, body = get_response(f"{SITE_URL.rstrip('/')}/{path}")
        if status != 200 or not body:
            return False

    return True


def make_api_server():
    sys.path.insert(0, str(ROOT / "CURA"))
    import api

    api.SITE_URL = SITE_URL
    api.validate_security_configuration()
    return ThreadingHTTPServer((api.HOST, api.PORT), api.ApiHandler)


class FrontendOnlyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "docs"), **kwargs)

    def translate_path(self, path):
        request_path = urlsplit(path).path
        if request_path.startswith("/docs/"):
            request_path = request_path[len("/docs"):]
        else:
            request_path = "/__not_found__"
        return super().translate_path(request_path)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def do_GET(self):
        request_path = urlsplit(self.path).path
        if request_path in ("/api/v1/latest", "/api/v1/history"):
            status, body = get_response(
                f"{API_BASE_URL}{self.path}",
                headers={"X-Device-Token": DEVICE_TOKEN},
            )
            if status is None:
                status = 503
                body = json.dumps({"error": "api indisponivel"}).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass
            return
        if request_path in ("/", "/index.html"):
            self.send_response(302)
            self.send_header("Location", "/docs/pages/index.html")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if not request_path.startswith("/docs/"):
            self.send_error(404, "Not found")
            return
        super().do_GET()

    def do_POST(self):
        request_path = urlsplit(self.path).path
        if not request_path.startswith("/api/v1/alerts/"):
            self.send_error(404, "Not found")
            return
        status, body = get_response(
            f"{API_BASE_URL}{self.path}",
            headers={
                "X-Device-Token": DEVICE_TOKEN,
                "Content-Length": "0",
            },
            data=b"",
            method="POST",
        )
        if status is None:
            status = 503
            body = json.dumps({"error": "api indisponivel"}).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass


def make_site_server():
    return ThreadingHTTPServer(("127.0.0.1", SITE_PORT), FrontendOnlyHandler)


def ensure_service(name, is_running, create_server, owned_servers):
    if is_running():
        print(f"{name}: ja ativo", flush=True)
        return

    server = create_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    owned_servers.append(server)
    print(f"{name}: iniciado", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    if args.check:
        api_ready = api_is_running()
        site_ready = site_is_running()
        print(f"API: {'online' if api_ready else 'offline'}")
        print(f"Site: {'online' if site_ready else 'offline'}")
        return 0 if api_ready and site_ready else 1

    owned_servers = []
    print("Iniciando servicos CUIDA+", flush=True)
    try:
        ensure_service("API", api_is_running, make_api_server, owned_servers)
        ensure_service("Site", site_is_running, make_site_server, owned_servers)
        print(
            f"CUIDA+ pronto: site {SITE_URL} | API {API_BASE_URL}",
            flush=True,
        )
        print("Leituras recebidas aparecem neste terminal; valores ao vivo aparecem no dashboard.", flush=True)
        threading.Event().wait()
    except KeyboardInterrupt:
        print("Encerrando servicos CUIDA+", flush=True)
    finally:
        for server in reversed(owned_servers):
            server.shutdown()
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())