"""เว็บเซิร์ฟเวอร์เล็ก ๆ สำหรับ Thai Fund Dashboard (ใช้ stdlib ล้วน ไม่ต้องลง Flask)

    python3 server.py              # โหมดจริง ต้องมี SEC_API_KEY ในไฟล์ .env
    python3 server.py --demo       # โหมดสาธิต ใช้ข้อมูลจำลอง ไม่ต้องใช้ API Key
    python3 server.py --port 8080

เหตุผลที่ต้องมี backend แทนที่จะให้หน้าเว็บยิง API ตรง ๆ
  - API Key จะได้ไม่หลุดไปอยู่ในหน้าเว็บ
  - เลี่ยงปัญหา CORS
  - รวมข้อมูลจากหลาย endpoint + cache + คำนวณสถิติให้เสร็จก่อนส่งไปวาดกราฟ
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import catalog as catalog_mod
import fund_service
import metrics
import quote_service
from sec_api import SecApiError, SecClient, load_dotenv

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"

_state: dict = {"client": None, "demo": False}
_client_lock = threading.Lock()
_bundle_cache: dict[tuple, tuple[float, dict]] = {}
_bundle_lock = threading.Lock()
BUNDLE_TTL = 900  # วินาที


def get_client():
    with _client_lock:
        if _state["client"] is None:
            _state["client"] = SecClient(use_cache=not _state.get("no_cache", False))
    return _state["client"]


def risk_free_rate() -> float:
    try:
        return float(os.environ.get("RISK_FREE_RATE", metrics.DEFAULT_RISK_FREE))
    except ValueError:
        return metrics.DEFAULT_RISK_FREE


def cached(key: tuple, builder):
    now = time.time()
    with _bundle_lock:
        hit = _bundle_cache.get(key)
        if hit and now - hit[0] < BUNDLE_TTL:
            return hit[1]
    value = builder()
    with _bundle_lock:
        _bundle_cache[key] = (now, value)
        if len(_bundle_cache) > 64:
            oldest = min(_bundle_cache, key=lambda k: _bundle_cache[k][0])
            _bundle_cache.pop(oldest, None)
    return value


# ---------------------------------------------------------------- API handlers
def integer_param(params: dict, name: str, default: int, maximum: int) -> int:
    try:
        value = int(params.get(name) or default)
        if not 1 <= value <= maximum:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise SecApiError(f"{name} ต้องเป็นจำนวนเต็มระหว่าง 1–{maximum}", 400) from exc
    return value


def api_meta(_: dict) -> dict:
    cat = catalog_mod.load_catalog()
    peers = catalog_mod.load_peers()
    return {
        "demo": _state["demo"],
        "catalog": {"available": bool(cat), "count": (cat or {}).get("count", 0), "generated_at": (cat or {}).get("generated_at")},
        "peers": {"available": bool(peers), "groups": len((peers or {}).get("groups", {})), "generated_at": (peers or {}).get("generated_at")},
        "history_years": fund_service.DEFAULT_HISTORY_YEARS,
        "risk_free_rate": risk_free_rate(),
        "source": "SEC Open Data API (https://secopendata.sec.or.th/)",
    }


def api_search(params: dict) -> dict:
    query = (params.get("q") or "").strip()
    limit = integer_param(params, "limit", 12, 50)
    if len(query) < 2:
        return {"results": []}
    cat = catalog_mod.load_catalog()
    if cat:
        return {"results": catalog_mod.search_catalog(cat, query, limit), "source": "catalog"}
    return {"results": fund_service.search_funds(get_client(), query, limit), "source": "api"}


def api_funds(params: dict) -> dict:
    """รายชื่อกองทุนสำหรับหน้า browse (ต้องรัน catalog.py --build ก่อนถึงจะครบทุกกอง)"""
    cat = catalog_mod.load_catalog()
    limit = integer_param(params, "limit", 300, 2000)
    query = (params.get("q") or "").strip()
    amc = (params.get("amc") or "").strip()
    policy = (params.get("policy") or "").strip()

    if not cat:
        results = fund_service.search_funds(get_client(), query or "กองทุน", limit=limit) if query else []
        return {"available": False, "funds": results, "amcs": [], "policies": [], "total": len(results)}

    funds = cat["funds"]
    if query:
        funds = catalog_mod.search_catalog(cat, query, limit=2000)
    if amc:
        funds = [f for f in funds if f.get("amc_th") == amc]
    if policy:
        funds = [f for f in funds if (f.get("policy") or "") == policy]

    amcs = sorted({f.get("amc_th", "") for f in cat["funds"] if f.get("amc_th")})
    policies = sorted({f.get("policy", "") for f in cat["funds"] if f.get("policy")})
    return {
        "available": True,
        "generated_at": cat.get("generated_at"),
        "total": len(funds),
        "funds": funds[:limit],
        "amcs": amcs,
        "policies": policies,
    }


def api_fund(params: dict) -> dict:
    code = (params.get("code") or "").strip()
    if not code:
        raise SecApiError("ต้องระบุรหัสกองทุน เช่น /api/fund?code=K-ATECH")
    class_name = (params.get("class") or "").strip() or None
    years = integer_param(params, "years", fund_service.DEFAULT_HISTORY_YEARS, 20)

    def build():
        bundle = fund_service.build_fund_bundle(
            get_client(), code, fund_class_name=class_name, years=years, risk_free=risk_free_rate()
        )
        bundle["peer"] = fund_service.peer_reference(catalog_mod.load_peers(), bundle["general"]["policy_desc"])
        return bundle

    return cached(("fund", code.upper(), class_name, years), build)


def api_compare(params: dict) -> dict:
    raw = params.get("codes") or ""
    codes = [c.strip() for c in raw.replace("\n", ",").split(",") if c.strip()][:8]
    if not codes:
        return {"funds": [], "errors": [], "window": params.get("window", "1Y")}
    window = (params.get("window") or "1Y").upper()
    years = integer_param(params, "years", fund_service.DEFAULT_HISTORY_YEARS, 20)

    def build():
        return fund_service.build_comparison(
            get_client(), codes, years=years, window=window, risk_free=risk_free_rate()
        )

    return cached(("compare", tuple(c.upper() for c in codes), window, years), build)


ROUTES = {
    "/api/quote": lambda params: quote_service.get_quote(params, get_client, _state["demo"]),
    "/api/history": lambda params: quote_service.get_history(params, get_client, _state["demo"]),
    "/api/meta": api_meta,
    "/api/search": api_search,
    "/api/funds": api_funds,
    "/api/fund": api_fund,
    "/api/compare": api_compare,
}


class Handler(BaseHTTPRequestHandler):
    server_version = "ThaiFundDashboard/1.0"

    def log_message(self, fmt: str, *args) -> None:  # เงียบกว่าเดิม
        if os.environ.get("SEC_VERBOSE"):
            super().log_message(fmt, *args)

    def _send(self, status: int, body: bytes, content_type: str, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        if path in ROUTES:
            try:
                self._json(200, ROUTES[path](params))
            except SecApiError as exc:
                status = (exc.status if exc.status in (400, 404) else 502) if path in ("/api/quote", "/api/history") else (400 if exc.status == 400 else 200)
                self._json(status, {"error": str(exc), "status": exc.status})
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                self._json(500, {"error": "เกิดข้อผิดพลาดภายในเซิร์ฟเวอร์ — ตรวจสอบ server log"})
            return

        # ---- static files ----
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC_DIR / rel).resolve()
        if not target.is_relative_to(STATIC_DIR.resolve()) or not target.is_file():
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
            ctype += "; charset=utf-8"
        self._send(200, target.read_bytes(), ctype, cache="no-cache")

    do_HEAD = do_GET


def main() -> None:
    parser = argparse.ArgumentParser(description="Thai Fund Dashboard — ข้อมูลจาก SEC Open Data API")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8765)))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--demo", action="store_true", help="ใช้ข้อมูลจำลอง ไม่ต้องมี API Key")
    parser.add_argument("--no-cache", action="store_true", help="ไม่ cache ผลลัพธ์จาก API ลง disk")
    args = parser.parse_args()

    load_dotenv()
    if args.demo:
        from demo_data import DemoClient

        _state["client"] = DemoClient()
        _state["demo"] = True
        print("⚠️  โหมดสาธิต: ข้อมูลทั้งหมดเป็นข้อมูลจำลอง ไม่ใช่ข้อมูลจริงของกองทุน")
    else:
        # Stock queries do not require a SEC key; initialize the fund client on demand.
        _state["no_cache"] = args.no_cache

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Thai Fund Dashboard → http://{args.host}:{args.port}  (กด Ctrl+C เพื่อหยุด)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nปิดเซิร์ฟเวอร์แล้ว")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
