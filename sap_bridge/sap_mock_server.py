"""Servidor SAP simulado para pruebas locales."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, Any

_DATA = {
    "ProductionOrders": [
        {"Order": "001", "Status": "OPEN", "Quantity": 10},
        {"Order": "002", "Status": "OPEN", "Quantity": 5},
    ]
}


class MockSAPHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        payload = getattr(self, "_payload", b"")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()

    def do_GET(self):  # noqa: N802
        resource = self._extract_resource()
        payload = _DATA.get(resource, [])
        body = json.dumps({"value": payload}).encode()
        self._payload = body
        self._set_headers()
        self.wfile.write(body)

    def do_POST(self):  # noqa: N802
        resource = self._extract_resource()
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(body.decode())
        except json.JSONDecodeError:
            data = {"raw": body.decode(errors="ignore")}
        _DATA.setdefault(resource, []).append(data)
        response = json.dumps({"status": "accepted"}).encode()
        self._payload = response
        self._set_headers(202)
        self.wfile.write(response)

    def log_message(self, format, *args):  # noqa: A003
        return

    def _extract_resource(self) -> str:
        path = self.path.split('?', 1)[0]
        return path.strip('/').split('/')[-1] or 'root'


def run_mock_server(host: str = "0.0.0.0", port: int = 8081):
    server = HTTPServer((host, port), MockSAPHandler)
    print(f"Mock SAP escuchando en http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    run_mock_server()
