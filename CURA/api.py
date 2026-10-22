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
SITE_URL = "http://127.0.0.1:8080/"
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "dev-token")
API_CORS_ORIGIN = "http://localhost:8080"
DATABASE = Path(os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "readings.sqlite3")))


def validate_security_configuration():
    if not DEVICE_TOKEN:
        raise ValueError("DEVICE_TOKEN nao pode ser vazio")
    if HOST not in {"127.0.0.1", "0.0.0.0"}:
        raise ValueError("API_HOST deve ser 127.0.0.1 ou 0.0.0.0")
    if HOST == "0.0.0.0" and (
        DEVICE_TOKEN == "dev-token" or len(DEVICE_TOKEN) < 32
    ):
        raise ValueError(
            "Ao expor a API na rede, defina DEVICE_TOKEN com pelo menos 32 caracteres"
        )


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
            connection.execute(
                """CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    reading_id INTEGER NOT NULL REFERENCES readings(id),
                    device_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    acknowledged_at TEXT,
                    resolved_at TEXT
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_alerts_open "
                "ON alerts(resolved_at, id DESC)"
            )
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_reading_type "
                "ON alerts(reading_id, alert_type)"
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
            connection.execute(
                """INSERT OR IGNORE INTO alerts (
                    reading_id, device_id, alert_type, created_at
                )
                SELECT id, device_id, 'panic', received_at
                FROM readings WHERE panic = 1"""
            )
            connection.execute(
                """INSERT OR IGNORE INTO alerts (
                    reading_id, device_id, alert_type, created_at
                )
                SELECT id, device_id, 'fall', received_at
                FROM (
                    SELECT id, device_id, received_at, fall_detected,
                           LAG(fall_detected, 1, 0) OVER (
                               PARTITION BY device_id ORDER BY id
                           ) AS previous_fall
                    FROM readings
                )
                WHERE fall_detected = 1 AND previous_fall = 0"""
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

        if path not in ("/api/v1/latest", "/api/v1/history", "/api/v1/health"):
            self.send_json(404, {"error": "nao encontrado"})
            return
        if not self.device_token_is_valid():
            self.send_json(401, {"error": "token invalido"})
            return

        with database_session() as connection:
            if path.endswith("health"):
                self.send_json(
                    200,
                    {"status": "ok", "database": "ok"},
                )
            elif path.endswith("latest"):
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
                alert_rows = connection.execute(
                    """SELECT id, reading_id, device_id, alert_type, created_at,
                              acknowledged_at, resolved_at
                       FROM alerts
                       WHERE resolved_at IS NULL
                       ORDER BY id DESC LIMIT 50"""
                ).fetchall()
                self.send_json(
                    200,
                    {
                        "reading": dict(latest) if latest else None,
                        "latest_panic": dict(latest_panic) if latest_panic else None,
                        "active_alerts": [
                            {
                                **dict(alert),
                                "status": (
                                    "acknowledged"
                                    if alert["acknowledged_at"]
                                    else "active"
                                ),
                            }
                            for alert in alert_rows
                        ],
                    },
                )
            else:
                rows = connection.execute(
                    "SELECT * FROM readings ORDER BY id DESC LIMIT 100"
                ).fetchall()
                self.send_json(200, {"readings": [dict(row) for row in rows]})

    def do_POST(self):
        path = urlparse(self.path).path
        if path.startswith("/api/v1/alerts/"):
            self.handle_alert_action(path)
            return
        if path != "/api/v1/readings":
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
                previous_fall = connection.execute(
                    """SELECT fall_detected FROM readings
                       WHERE device_id = ? ORDER BY id DESC LIMIT 1""",
                    (payload.get("device_id", "pulseira-01"),),
                ).fetchone()
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
                alert_types = []
                if reading["panic"]:
                    alert_types.append("panic")
                if (
                    reading["fall_detected"]
                    and not (previous_fall and previous_fall["fall_detected"])
                ):
                    alert_types.append("fall")
                for alert_type in alert_types:
                    connection.execute(
                        """INSERT INTO alerts (
                            reading_id, device_id, alert_type, created_at
                        ) VALUES (?, ?, ?, ?)""",
                        (
                            reading["id"],
                            reading["device_id"],
                            alert_type,
                            reading["received_at"],
                        ),
                    )
            print(
                f"[API] Telemetria armazenada: id={reading['id']} "
                f"alerta={reading['panic']} status={reading['status']}",
                flush=True,
            )
            self.send_json(201, {"reading": reading})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self.send_json(400, {"error": str(error)})

    def handle_alert_action(self, path):
        if not self.device_token_is_valid():
            self.send_json(401, {"error": "token invalido"})
            return

        parts = path.split("/")
        if len(parts) != 6 or parts[3] != "alerts":
            self.send_json(404, {"error": "nao encontrado"})
            return
        try:
            alert_id = int(parts[4])
        except ValueError:
            self.send_json(400, {"error": "id de alerta invalido"})
            return
        action = parts[5]
        if alert_id < 1 or action not in {"acknowledge", "resolve"}:
            self.send_json(404, {"error": "acao de alerta nao encontrada"})
            return

        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        column = "acknowledged_at" if action == "acknowledge" else "resolved_at"
        with database_session() as connection:
            cursor = connection.execute(
                f"UPDATE alerts SET {column} = ? WHERE id = ? AND resolved_at IS NULL "
                f"AND {column} IS NULL",
                (timestamp, alert_id),
            )
            alert = connection.execute(
                """SELECT id, reading_id, device_id, alert_type, created_at,
                          acknowledged_at, resolved_at
                   FROM alerts WHERE id = ?""",
                (alert_id,),
            ).fetchone()
        if alert is None:
            self.send_json(404, {"error": "alerta nao encontrado"})
            return
        alert_data = dict(alert)
        alert_data["status"] = (
            "resolved"
            if alert["resolved_at"]
            else "acknowledged"
            if alert["acknowledged_at"]
            else "active"
        )
        self.send_json(200, {"alert": alert_data, "updated": cursor.rowcount == 1})

    def log_message(self, format_string, *args):
        request_line = args[0] if args else ""
        if request_line.startswith(
            ("GET /api/v1/latest", "GET /api/v1/history", "GET /api/v1/health")
        ):
            return
        print(f"{self.address_string()} - {format_string % args}")


if __name__ == "__main__":
    validate_security_configuration()
    with database_session():
        pass
    print(f"API e painel em http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), ApiHandler).serve_forever()
