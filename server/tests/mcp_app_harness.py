"""A stand-in MCP Apps host for the research canvas (api/mcp_canvas.html), to
see and test it without Claude: a page that frames the app the way a host does
(sandboxed iframe, JSON-RPC over postMessage), answers ui/initialize, hands it
a tool result, and passes its tools/call on to a real DeepLit MCP server.

    LITSTORM_MCP_URL=http://127.0.0.1:8095/api/mcp LITSTORM_MCP_TOKEN=dlk_... \\
        python server/tests/mcp_app_harness.py [port] [settings file]

(a settings file, if given, holds the LITSTORM_MCP_URL= and LITSTORM_MCP_TOKEN=
lines, as tests/canvas_demo_server.py prints them)

then open http://127.0.0.1:8897/?run=<research id>&theme=dark&locale=th
(no run: the app plays its demo; /app#demo=deep plays one kind).
Every message both ways is listed under the frame, for checking the wire.
"""

import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APP = pathlib.Path(__file__).resolve().parents[1] / "src" / "litstorm" / "api" / "mcp_canvas.html"
MCP_URL = os.environ.get("LITSTORM_MCP_URL", "http://127.0.0.1:8095/api/mcp")
TOKEN = os.environ.get("LITSTORM_MCP_TOKEN", "")

HOST_PAGE = """<!doctype html><meta charset="utf-8"><title>MCP Apps harness</title>
<style>body{font:13px system-ui;margin:16px;background:#888;}iframe{width:min(760px,100%);border:0;border-radius:12px;
background:#fff;display:block;height:300px}pre{font-size:11px;max-height:260px;overflow:auto;background:#111;color:#9f9;padding:8px}</style>
<iframe id="app" sandbox="allow-scripts"></iframe><pre id="wire"></pre>
<script>
const q = new URLSearchParams(location.search), frame = document.getElementById("app"), wire = document.getElementById("wire");
// srcdoc, as a host's sandbox does: an opaque origin, and the CSP of an app that declares no domains.
fetch("/app").then((r) => r.text()).then((html) => {
  frame.srcdoc = html.replace("<head>", '<head><meta http-equiv="Content-Security-Policy" content="' +
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:" + '">');
});
const log = (dir, m) => { wire.textContent = dir + " " + JSON.stringify(m).slice(0, 300) + "\\n" + wire.textContent; };
const toApp = (m) => { log("host->app", m); frame.contentWindow.postMessage(m, "*"); };
let rpcId = 0;
async function mcp(method, params) {
  const r = await fetch("/mcp", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({jsonrpc: "2.0", id: ++rpcId, method, params})});
  return (await r.json());
}
window.addEventListener("message", async (e) => {
  if (e.source !== frame.contentWindow) return;
  const m = e.data; log("app->host", m);
  if (m.method === "ui/initialize") {
    toApp({jsonrpc: "2.0", id: m.id, result: {protocolVersion: "2026-01-26", hostInfo: {name: "harness", version: "1"},
      hostCapabilities: {serverTools: {}, openLinks: {}},
      hostContext: {theme: q.get("theme") || "light", locale: q.get("locale") || "en-US", displayMode: "inline",
        availableDisplayModes: ["inline", "fullscreen"]}}});
  } else if (m.method === "ui/notifications/initialized") {
    const run = q.get("run");
    if (!run) return;
    toApp({jsonrpc: "2.0", method: "ui/notifications/tool-input", params: {arguments: {id: run, wait_seconds: 0}}});
    const out = await mcp("tools/call", {name: "research_status", arguments: {id: run, wait_seconds: 0}});
    toApp({jsonrpc: "2.0", method: "ui/notifications/tool-result", params: out.result});
  } else if (m.method === "tools/call") {
    const out = await mcp("tools/call", m.params);
    toApp(out.error ? {jsonrpc: "2.0", id: m.id, error: out.error} : {jsonrpc: "2.0", id: m.id, result: out.result});
  } else if (m.method === "ui/notifications/size-changed") {
    frame.style.height = m.params.height + "px";
  } else if (m.id != null) {
    toApp({jsonrpc: "2.0", id: m.id, result: {}});
  }
});
</script>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, kind):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path == "/":
            return self._send(200, HOST_PAGE, "text/html; charset=utf-8")
        if path == "/app":
            # The CSP a host gives an app with no declared domains: nothing from the network.
            html = APP.read_text(encoding="utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:")
            data = html.encode()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            return self.wfile.write(data)
        self._send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/mcp":
            return self._send(404, "not found", "text/plain")
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        req = urllib.request.Request(MCP_URL, data=body, method="POST", headers={
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {TOKEN}",
        })
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                raw = r.read().decode()
        except urllib.error.HTTPError as e:
            return self._send(200, json.dumps({"jsonrpc": "2.0", "id": None,
                                               "error": {"code": e.code, "message": e.read().decode()[:300]}}),
                              "application/json")
        if "data:" in raw:
            raw = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")][-1]
        self._send(200, raw, "application/json")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8897
    if len(sys.argv) > 2:
        for line in pathlib.Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key == "LITSTORM_MCP_URL":
                MCP_URL = value.strip()
            elif key == "LITSTORM_MCP_TOKEN":
                TOKEN = value.strip()
    print(f"http://127.0.0.1:{port}/  ->  {MCP_URL}")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
