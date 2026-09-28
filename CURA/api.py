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
DEVICE_TOKEN = os.getenv("DEVICE_TOKEN", "dev-token")
DATABASE = Path(os.getenv("DATABASE_PATH", str(Path(__file__).resolve().parent / "readings.sqlite3")))

PAGE = """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Monitor da pulseira</title>
  <style>
    body{font:16px system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 20px;background:#f2f5f3;color:#17211b}
    h1{font-size:1.7rem}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px}
    article{padding:18px;background:white;border:1px solid #d9e1dc;border-radius:6px}
    article strong{display:block;font-size:1.7rem;margin-top:8px}#status{font-weight:700}
    #panic{color:#a21d24;font-weight:700}#panic:empty{display:none}.muted{color:#5c6a61;font-size:.9rem}
  </style>
</head>
<body>
  <h1>Monitor da pulseira</h1>
  <p id="status">Carregando...</p>
  <main>
    <article>Saturacao estimada<strong id="spo2">--</strong></article>
    <article>Frequencia do pulso<strong id="heart">--</strong></article>
    <article>Temperatura de contato<strong id="temperature">--</strong></article>
    <article>Tendencia termica<strong id="trend">--</strong></article>
  </main>
  <p id="panic" aria-live="assertive"></p><p class="muted" id="updated"></p>
  <script>
    const show = (id, value, suffix = "") => {
      document.getElementById(id).textContent = value == null ? "Sem leitura" : `${value}${suffix}`;
    };
    async function refresh() {
      try {
        const response = await fetch('/api/v1/latest');
        const data = await response.json();
        if (!data.reading) {
          document.getElementById('status').textContent = 'Aguardando dados da pulseira';
          return;
        }
        const item = data.reading;
        show('spo2', item.spo2_percent, '%');
        show('heart', item.heart_rate_bpm, ' bpm');
        show('temperature', item.temperature_c, ' C');
        show('trend', item.temperature_trend);
        document.getElementById('status').textContent = `Estado: ${item.status}`;
        const alert = data.latest_panic;
        if (alert) {
          const details = [
            alert.spo2_percent == null ? 'SpO2 sem leitura' : `SpO2 ${alert.spo2_percent}%`,
            alert.heart_rate_bpm == null ? 'pulso sem leitura' : `${alert.heart_rate_bpm} bpm`,
            alert.temperature_c == null ? 'temperatura sem leitura' : `${alert.temperature_c} C`
          ].join(' | ');
          document.getElementById('panic').textContent = `ALERTA MANUAL (${alert.received_at}): ${details}`;
        } else {
          document.getElementById('panic').textContent = '';
        }
        document.getElementById('updated').textContent = `Recebido em ${item.received_at}`;
      } catch {
        document.getElementById('status').textContent = 'API indisponivel';
      }
    }
    refresh();
    setInterval(refresh, 10000);
  </script>
</body>
</html>"""


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
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
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
            self.send_json(201, {"reading": reading})
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self.send_json(400, {"error": str(error)})

    def log_message(self, format_string, *args):
        print(f"{self.address_string()} - {format_string % args}")


if __name__ == "__main__":
    with database_session():
        pass
    print(f"API e painel em http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), ApiHandler).serve_forever()
