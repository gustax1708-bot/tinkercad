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
API_URL = "http://127.0.0.1:8000/api/v1/latest"
SITE_URL = "http://127.0.0.1:8080/frontend/pages/home.html"
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "dev-token")


def get_response(url, headers=None):
    try:
        request = Request(url, headers=headers or {})
        with urlopen(request, timeout=1) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()
    except URLError:
        return None, b""


def api_is_running():
    status, body = get_response(
        API_URL, headers={"X-Device-Token": DEVICE_TOKEN}
    )
    if status != 200:
        return False
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return "reading" in payload and "latest_panic" in payload


def site_is_running():
    status, body = get_response(SITE_URL)
    if status != 200 or b"<!doctype html>" not in body[:128].lower():
        return False

    for path in ("/CURA/readings.sqlite3", "/.git/config"):
        status, _ = get_response(f"http://127.0.0.1:8080{path}")
        if status not in (403, 404):
            return False
    return True


def make_api_server():
    sys.path.insert(0, str(ROOT / "CURA"))
    import api

    api.validate_security_configuration()
    return ThreadingHTTPServer((api.HOST, api.PORT), api.ApiHandler)


class FrontendOnlyHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "frontend"), **kwargs)

    def translate_path(self, path):
        request_path = urlsplit(path).path
        if request_path.startswith("/frontend/"):
            request_path = request_path[len("/frontend"):]
        elif request_path in ("/", "/frontend", "/frontend/"):
            request_path = "/pages/home.html"
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
                f"http://127.0.0.1:8000{self.path}",
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
        if request_path in ("/", "/frontend", "/frontend/"):
            self.send_response(302)
            self.send_header("Location", "/frontend/pages/home.html")
            self.end_headers()
            return
        if not request_path.startswith("/frontend/"):
            self.send_error(404, "Not found")
            return
        super().do_GET()


def make_site_server():
    return ThreadingHTTPServer(("127.0.0.1", 8080), FrontendOnlyHandler)


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
        print(f"CUIDA+ pronto: site {SITE_URL} | API http://localhost:8000", flush=True)
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