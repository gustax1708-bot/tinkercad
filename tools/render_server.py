import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = ROOT / "frontend"
sys.path.insert(0, str(ROOT / "CURA"))

os.environ["API_HOST"] = "0.0.0.0"
os.environ["API_PORT"] = os.getenv("PORT", "10000")

import api


class RenderHandler(SimpleHTTPRequestHandler):
    send_json = api.ApiHandler.send_json
    do_OPTIONS = api.ApiHandler.do_OPTIONS
    do_POST = api.ApiHandler.do_POST
    log_message = api.ApiHandler.log_message

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        SimpleHTTPRequestHandler.end_headers(self)

    def device_token_is_valid(self):
        if (
            self.command == "GET"
            and urlsplit(self.path).path in ("/api/v1/latest", "/api/v1/history")
        ):
            return True
        return api.ApiHandler.device_token_is_valid(self)

    def translate_path(self, path):
        request_path = urlsplit(path).path
        if request_path == "/":
            request_path = "/pages/index.html"
        elif request_path.startswith("/frontend/"):
            request_path = request_path[len("/frontend"):]

        relative_path = Path(unquote(request_path).lstrip("/"))
        resolved_path = (FRONTEND_ROOT / relative_path).resolve()
        if resolved_path != FRONTEND_ROOT and FRONTEND_ROOT not in resolved_path.parents:
            return str(FRONTEND_ROOT / "__not_found__")
        return str(resolved_path)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path in ("/api/v1/latest", "/api/v1/history"):
            return api.ApiHandler.do_GET(self)
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/frontend/pages/index.html")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        if path == "/healthz":
            body = b"ok\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        return super().do_GET()


def main():
    api.validate_security_configuration()
    with api.database_session():
        pass

    server = ThreadingHTTPServer((api.HOST, api.PORT), RenderHandler)
    print(f"CUIDA+ pronto em http://{api.HOST}:{api.PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Encerrando CUIDA+", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
