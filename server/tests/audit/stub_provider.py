"""Task 6 of the 2026-10-24 audit: a stand-in provider that fails on purpose. No paid calls.

    cd server && uv run python tests/audit/stub_provider.py [--port 9099] [--slow-seconds 75]

One tiny stdlib HTTP server that answers as an OpenAI-compatible chat endpoint and as a SearXNG
search endpoint. The first path segment chooses what it does:

    /429/v1/chat/completions    429 rate limit              /429/search     429
    /401/v1/chat/completions    401 invalid api key         /401/search     401
    /500/v1/chat/completions    500                         /500/search     500
    /slow/v1/chat/completions   sleeps, then answers        /slow/search    sleeps, then answers {"results": []}
    /ok/v1/chat/completions     a canned answer             /ok/search      {"results": []}

Point an `openai-compatible` credential's api_base at http://host.docker.internal:9099/<mode>/v1
(containers reach the host by that name) and a SearXNG provider's endpoint at
http://host.docker.internal:9099/<mode>/search. Every request is logged (method, path, no body).
"""

import argparse
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SLOW = 75.0
ERRORS = {
    "429": (429, {"error": {"message": "Rate limit reached (stub)", "type": "rate_limit_error", "code": "rate_limit_exceeded"}}),
    "401": (401, {"error": {"message": "Incorrect API key provided (stub)", "type": "invalid_request_error", "code": "invalid_api_key"}}),
    "500": (500, {"error": {"message": "The server had an error (stub)", "type": "server_error"}}),
}
COUNT = {}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            if status == 429:
                self.send_header("Retry-After", "1")
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass  # the caller gave up first, which is what the slow mode is for

    def _handle(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        mode = self.path.lstrip("/").split("/", 1)[0]
        kind = "search" if "/search" in self.path else "chat"
        with LOCK:
            COUNT[(mode, kind)] = COUNT.get((mode, kind), 0) + 1
            n = COUNT[(mode, kind)]
        print(f"{time.strftime('%H:%M:%S')} {self.command} {self.path.split('?')[0]} #{n}", flush=True)
        if mode in ERRORS:
            return self._send(*ERRORS[mode])
        if mode == "slow":
            time.sleep(SLOW)
        if kind == "search":
            return self._send(200, {"results": []})
        return self._send(200, {
            "id": "stub", "object": "chat.completion", "created": int(time.time()), "model": "stub",
            "choices": [{"index": 0, "finish_reason": "stop",
                         "message": {"role": "assistant", "content": "Stub answer."}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        })

    do_GET = do_POST = _handle  # noqa: N815


def main():
    global SLOW
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=9099)
    p.add_argument("--slow-seconds", type=float, default=SLOW)
    a = p.parse_args()
    SLOW = a.slow_seconds
    print(f"stub provider on 0.0.0.0:{a.port}, slow={SLOW}s", flush=True)
    ThreadingHTTPServer(("0.0.0.0", a.port), Handler).serve_forever()


if __name__ == "__main__":
    sys.exit(main())
