import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "8000"))
SITE_URL = os.getenv("SITE_URL", "http://localhost:8080/frontend/pages/home.html")
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "dev-token")
API_CORS_ORIGIN = os.getenv("API_CORS_ORIGIN", "*")
DATABASE = Path(os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "readings.sqlite3")))


@contextmanager
def database_session():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS readings (
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
        with connection:
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
    device_id = payload.get("device_id", "pulseira-01")
    if not isinstance(device_id, str) or not 1 <= len(device_id) <= 64:
        raise ValueError("device_id invalido")

    panic = valid_boolean(payload, "panic")
    contact = valid_boolean(payload, "sensor_contact")
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
        "panic": panic,
        "sensor_contact": contact,
        "status": "panico" if panic else ("sem_contato" if not contact else "normal_demo"),
        "temperature_trend": trend,
    }


class ApiHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", API_CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Device-Token")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", API_CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Device-Token")
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

        with database_session() as connection:
            if path.endswith("latest"):
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
        if self.headers.get("X-Device-Token") != DEVICE_TOKEN:
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
                        temperature_c, panic, sensor_contact, status, temperature_trend
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        reading["device_id"], reading["received_at"],
                        reading["spo2_percent"], reading["heart_rate_bpm"],
                        reading["temperature_c"], int(reading["panic"]),
                        int(reading["sensor_contact"]), reading["status"],
                        reading["temperature_trend"],
                    ),
                )
                reading["id"] = cursor.lastrowid
            print(
                "[API] Leitura recebida: "
                f"device={reading['device_id']} "
                f"SpO2={reading['spo2_percent']}% "
                f"pulso={reading['heart_rate_bpm']} bpm "
                f"temperatura={reading['temperature_c']} C "
                f"panico={reading['panic']}",
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
    with database_session():
        pass
    print(f"API e painel em http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), ApiHandler).serve_forever()
