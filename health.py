"""Health endpoint support for Streamlit deployments."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

_health_thread = None


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_health_server(host: str = "0.0.0.0", port: int = 8080):
    server = HTTPServer((host, port), HealthHandler)
    server.serve_forever()


def start_health_server():
    global _health_thread
    if _health_thread is not None and _health_thread.is_alive():
        return _health_thread

    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    _health_thread = health_thread
    return _health_thread
