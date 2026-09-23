import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import gmg_api
import gog_api
import steam_api

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "docs")

PLATFORMS = {
    "steam": (steam_api, os.path.join(STATIC_DIR, "data.json")),
    "gog": (gog_api, os.path.join(STATIC_DIR, "gog_data.json")),
    "gmg": (gmg_api, os.path.join(STATIC_DIR, "gmg_data.json")),
}

_lock = threading.Lock()

MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path

        for platform, (module, data_path) in PLATFORMS.items():
            if path == f"/api/{platform}/deals":
                with _lock:
                    if not os.path.exists(data_path):
                        try:
                            module.fetch_and_save(data_path)
                        except Exception as exc:
                            self._send_json({"error": str(exc)}, status=502)
                            return
                    with open(data_path, "r", encoding="utf-8") as f:
                        payload = json.load(f)
                self._send_json(payload)
                return

            if path == f"/api/{platform}/refresh":
                with _lock:
                    try:
                        payload = module.fetch_and_save(data_path)
                    except Exception as exc:
                        self._send_json({"error": str(exc)}, status=502)
                        return
                self._send_json(payload)
                return

        if path == "/":
            path = "/index.html"

        file_path = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
        is_inside_static = file_path == STATIC_DIR or file_path.startswith(STATIC_DIR + os.sep)
        if not is_inside_static or not os.path.isfile(file_path):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        ext = os.path.splitext(file_path)[1]
        self._send_file(file_path, MIME_TYPES.get(ext, "application/octet-stream"))

    def log_message(self, format, *args):
        pass


def main():
    port = int(os.environ.get("PORT", 8000))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"게임 할인 목록 서버 실행 중: http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
