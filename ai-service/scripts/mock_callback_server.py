import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


STORE = Path(__file__).resolve().parents[1] / "tmp" / "external_mock_callbacks.jsonl"
STORE.parent.mkdir(parents=True, exist_ok=True)


class CallbackHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")

        with STORE.open("a", encoding="utf-8") as fp:
            fp.write(body + "\n")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", 8010), CallbackHandler)
    print("mock callback server listening on http://127.0.0.1:8010/callback")
    server.serve_forever()
