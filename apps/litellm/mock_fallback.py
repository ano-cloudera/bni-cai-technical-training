import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.dumps(
            {
                "id": "training-fallback",
                "choices": [
                    {"message": {"role": "assistant", "content": "Controlled workshop fallback response."}}
                ],
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", int(os.getenv("CDSW_APP_PORT", "8080"))), Handler).serve_forever()
