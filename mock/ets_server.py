#!/usr/bin/env python3
"""Mock ЕТС SMS serveri — HAQIQIY HTTP (127.0.0.1:8472).
Rejimlar (env ETS_MOCK_REJIM yoki ?rejim=): ok | 429 | 500 | sekin.
Shunda shlyuz N1 retry/timeout/429 kodi mockda ham sinaladi.

  python3 mock/ets_server.py [--port 8472]
"""
import os
import json
import time
import argparse
import itertools
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_id = itertools.count(1)
_holatlar = {}  # message_id -> holat


def _rejim(qs):
    if "rejim=" in qs:
        for p in qs.split("&"):
            if p.startswith("rejim="):
                return p.split("=", 1)[1]
    return os.environ.get("ETS_MOCK_REJIM", "ok")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # jim

    def _javob(self, kod, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        yol, _, qs = self.path.partition("?")
        rejim = _rejim(qs)
        uz = int(self.headers.get("Content-Length", 0))
        gavda = self.rfile.read(uz) if uz else b"{}"
        try:
            payload = json.loads(gavda.decode("utf-8"))
        except Exception:
            payload = {}

        if yol == "/send":
            if rejim == "429":
                return self._javob(429, {"xato": "too many requests", "retry_after": 2})
            if rejim == "500":
                return self._javob(500, {"xato": "server error"})
            if rejim == "sekin":
                time.sleep(3)
            mid = f"mock-ets-{next(_id)}"
            _holatlar[mid] = "yuborildi"
            return self._javob(200, {"message_id": mid, "holat": "yuborildi",
                                     "narx_som": 95, "telefon": payload.get("telefon")})

        if yol == "/status":
            mid = payload.get("message_id")
            # birinchi so'rovda yuborildi, keyingisida yetkazildi
            hol = _holatlar.get(mid, "notfound")
            if hol == "yuborildi":
                _holatlar[mid] = "yetkazildi"
            return self._javob(200, {"message_id": mid, "holat": hol})

        return self._javob(404, {"xato": "noma'lum yo'l"})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8472)
    args = ap.parse_args(argv)
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"mock ЕТС: http://127.0.0.1:{args.port} rejim={os.environ.get('ETS_MOCK_REJIM', 'ok')}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()


if __name__ == "__main__":
    main()
