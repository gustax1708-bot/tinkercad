import json
import hmac
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


HOST = os.getenv("API_HOST", "127.0.0.1")
PORT = int(os.getenv("API_PORT", "8000"))
SITE_URL = os.getenv("SITE_URL", "/docs/pages/index.html")
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "dev-token")
API_CORS_ORIGIN = os.getenv("API_CORS_ORIGIN", "http://localhost:8080")
DATABASE = Path(os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "readings.sqlite3")))


def validate_security_configuration():
    if not DEVICE_TOKEN:
        raise ValueError("DEVICE_TOKEN nao pode ser vazio")
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if HOST not in local_hosts and DEVICE_TOKEN == "dev-token":
        raise ValueError("Defina um DEVICE_TOKEN proprio antes de expor a API na rede")


@contextmanager
def database_session():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    spo2_percent REAL,
                    heart_rate_bpm REAL,
                    temperature_c REAL,
                    battery_percent REAL,
                    battery_voltage REAL,
                    acceleration_g REAL,
                    motion_active INTEGER NOT NULL DEFAULT 0,
                    fall_detected INTEGER NOT NULL DEFAULT 0,
                    panic INTEGER NOT NULL,
                    sensor_contact INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    temperature_trend TEXT NOT NULL
                )"""
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(readings)")
            }
            new_columns = {
                "battery_percent": "REAL",
                "battery_voltage": "REAL",
                "acceleration_g": "REAL",
                "motion_active": "INTEGER NOT NULL DEFAULT 0",
                "fall_detected": "INTEGER NOT NULL DEFAULT 0",
            }
            for name, definition in new_columns.items():
                if name not in columns:
                    connection.execute(
                        f"ALTER TABLE readings ADD COLUMN {name} {definition}"
                    )
            yield connection
    finally:
        connection.close()


def valid_number(value, minimum, maximum):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Leitura numerica invalida")
    if not minimum <= value <= maximum:
        raise ValueError("Leitura fora do intervalo permitido")
    return float(value)


def valid_boolean(payload, key):
    value = payload.get(key, False)
    if not isinstance(value, bool):
        raise ValueError(f"{key} deve ser booleano")
    return value

def interpret(payload, connection):
    spo2 = valid_number(payload.get("spo2_percent"), 50, 100)
    heart_rate = valid_number(payload.get("heart_rate_bpm"), 25, 240)
    temperature = valid_number(payload.get("temperature_c"), 0, 50)
    battery_percent = valid_number(payload.get("battery_percent"), 0, 100)
    battery_voltage = valid_number(payload.get("battery_voltage"), 2.5, 5.0)
    acceleration = valid_number(payload.get("acceleration_g"), 0, 32)
    device_id = payload.get("device_id", "pulseira-01")
    if not isinstance(device_id, str) or not 1 <= len(device_id) <= 64:
        raise ValueError("device_id invalido")

    panic = valid_boolean(payload, "panic")
    contact = valid_boolean(payload, "sensor_contact")
    motion_active = valid_boolean(payload, "motion_active")
    fall_detected = valid_boolean(payload, "fall_detected")
    trend = "estavel"
    if temperature is not None:
        previous = connection.execute(
            """SELECT temperature_c FROM readings
               WHERE device_id = ? AND temperature_c IS NOT NULL
               ORDER BY id DESC LIMIT 1""",
            (device_id,),
        ).fetchone()
        if previous:
            difference = temperature - previous["temperature_c"]
            if difference >= 0.3:
                trend = "subindo"
            elif difference <= -0.3:
                trend = "caindo"

    return {
        "device_id": device_id,
        "received_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spo2_percent": spo2,
        "heart_rate_bpm": heart_rate,
        "temperature_c": temperature,
        "battery_percent": battery_percent,
        "battery_voltage": battery_voltage,
        "acceleration_g": acceleration,
        "panic": panic,
        "sensor_contact": contact,
        "motion_active": motion_active,
        "fall_detected": fall_detected,
        "status": (
            "panico"
            if panic
            else "queda_possivel"
            if fall_detected
            else "sem_contato"
            if not contact
            else "normal_demo"
        ),
        "temperature_trend": trend,
    }
class ApiHandler(BaseHTTPRequestHandler):
    def device_token_is_valid(self):
        supplied_token = self.headers.get("X-Device-Token", "")
        return hmac.compare_digest(supplied_token, DEVICE_TOKEN)

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        super().end_headers()

    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", API_CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Device-Token")
        self.send_header("Vary", "Origin")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        self.send_response(204)
        if origin == API_CORS_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", API_CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Device-Token")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_response(302)
            self.send_header("Location", SITE_URL)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        if path not in ("/api/v1/latest", "/api/v1/history"):
            self.send_json(404, {"error": "nao encontrado"})
            return
        if not self.device_token_is_valid():
            self.send_json(401, {"error": "token invalido"})
            return

        with database_session() as connection:
            if path.endswith("latest"):
                latest = connection.execute(
                    "SELECT * FROM readings WHERE panic = 0 ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if latest is None:
                    latest = connection.execute(
                        "SELECT * FROM readings ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                latest_panic = connection.execute(
                    "SELECT * FROM readings WHERE panic = 1 ORDER BY id DESC LIMIT 1"
                ).fetchone()
                self.send_json(
                    200,
                    {
                        "reading": dict(latest) if latest else None,
                        "latest_panic": dict(latest_panic) if latest_panic else None,
                    },
                )
            else:
                rows = connection.execute(
                    "SELECT * FROM readings ORDER BY id DESC LIMIT 100"
                ).fetchall()
                self.send_json(200, {"readings": [dict(row) for row in rows]})

    def do_POST(self):
        if urlparse(self.path).path != "/api/v1/readings":
            self.send_json(404, {"error": "nao encontrado"})
            return
        if not self.device_token_is_valid():
            self.send_json(401, {"error": "token invalido"})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 4096:
                raise ValueError("tamanho do corpo invalido")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("o corpo deve ser um objeto JSON")
            with database_session() as connection:
                reading = interpret(payload, connection)
                cursor = connection.execute(
                    """INSERT INTO readings (
                        device_id, received_at, spo2_percent, heart_rate_bpm,
                        temperature_c, battery_percent, battery_voltage,
                        acceleration_g, motion_active, fall_detected, panic,
                        sensor_contact, status, temperature_trend
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        reading["device_id"], reading["received_at"],
                        reading["spo2_percent"], reading["heart_rate_bpm"],
                        reading["temperature_c"], reading["battery_percent"],
                        reading["battery_voltage"], reading["acceleration_g"],
                        int(reading["motion_active"]),
                        int(reading["fall_detected"]), int(reading["panic"]),
                        int(reading["sensor_contact"]), reading["status"],
                        reading["temperature_trend"],
                    ),
                )
                reading["id"] = cursor.lastrowid
            print(
                f"[API] Telemetria armazenada: id={reading['id']} "
                f"alerta={reading['panic']} status={reading['status']}",
                flush=True,
            )
            self.send_json(201, {"reading": reading})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self.send_json(400, {"error": str(error)})

    def log_message(self, format_string, *args):
        request_line = args[0] if args else ""
        if request_line.startswith(("GET /api/v1/latest", "GET /api/v1/history")):
            return
        print(f"{self.address_string()} - {format_string % args}")


if __name__ == "__main__":
    validate_security_configuration()
    with database_session():
        pass
    print(f"API e painel em http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), ApiHandler).serve_forever()
