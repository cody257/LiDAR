"""lidar-arch container entrypoint — a tiny stdlib HTTP server on :PORT.

The Cloudflare Worker proxies requests here:
  POST /run  {bbox:[w,s,e,n], resource:"<ept-url|name>", products:["lrm","rrim",...]}
        -> 200 { bbox, products:[...], pngs:{ name: base64-png } }
  GET  /health -> {ok:true}

Outputs are returned as base64 PNGs so the Worker (not this container) owns R2 —
keeps the container stateless and credential-free, which makes local dev trivial.
"""
import base64
import json
import os
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))
PNG_STEM = {"openness": "opns"}  # the CLI writes opns.png for the openness product


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):  # keep the container logs quiet
        pass

    def do_GET(self):
        if self.path == "/health":
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/run":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length) or b"{}")
            bbox = req["bbox"]
            if not (isinstance(bbox, list) and len(bbox) == 4):
                return self._json(400, {"error": "bbox must be [w, s, e, n]"})
            resource = req.get("resource")
            products = req.get("products") or ["lrm", "rrim", "svf"]
        except Exception as exc:  # noqa: BLE001 - report any bad input
            return self._json(400, {"error": f"bad request: {exc}"})

        with tempfile.TemporaryDirectory() as out:
            cmd = ["lidar-arch", "run", "--bbox", *[str(x) for x in bbox],
                   "--out", out, "--products", ",".join(products)]
            if resource:
                cmd += ["--resource", str(resource)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                return self._json(500, {"error": "pipeline failed",
                                        "detail": (proc.stderr or proc.stdout)[-3000:]})
            pngs = {}
            for p in products:
                path = os.path.join(out, f"{PNG_STEM.get(p, p)}.png")
                if os.path.exists(path):
                    with open(path, "rb") as fh:
                        pngs[p] = base64.b64encode(fh.read()).decode()
            if not pngs:
                return self._json(500, {"error": "no PNG outputs produced"})
            return self._json(200, {"bbox": bbox, "products": list(pngs), "pngs": pngs})


if __name__ == "__main__":
    print(f"lidar-arch container listening on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
