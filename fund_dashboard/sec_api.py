"""Client สำหรับ SEC Open Data API (secopendata.sec.or.th) เวอร์ชัน v2

ใช้เฉพาะ standard library ของ Python เท่านั้น ไม่ต้อง pip install อะไรเพิ่ม

เอกสาร API: https://secopendata.sec.or.th/  (ต้องสมัครและขอ API Key ก่อน)
ทุก request ต้องแนบ header `Ocp-Apim-Subscription-Key: <API KEY ของเรา>`
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterator

BASE_URL = os.environ.get("SEC_API_BASE_URL", "https://api.sec.or.th")
ROOT = Path(__file__).resolve().parent
CACHE_DIR = Path(os.environ.get("SEC_CACHE_DIR", ROOT / "cache"))
HTTP_CACHE_DIR = CACHE_DIR / "http"

# TTL ของ cache (วินาที) แยกตามกลุ่มข้อมูล เพราะข้อมูลแต่ละชุดอัปเดตไม่เท่ากัน
TTL_BY_PREFIX = {
    "/v2/fund/daily-info/nav": 6 * 3600,          # NAV รายวัน
    "/v2/fund/daily-info": 12 * 3600,
    "/v2/fund/factsheet": 24 * 3600,              # factsheet อัปเดตรายเดือน
    "/v2/fund/general-info": 24 * 3600,
    "/v2/fund/outstanding": 24 * 3600,
}
DEFAULT_TTL = 12 * 3600

MAX_PAGE_SIZE = 100


class SecApiError(RuntimeError):
    """ยิง API ไม่สำเร็จ (key ผิด, โควตาหมด, endpoint เปลี่ยน ฯลฯ)"""

    def __init__(self, message: str, status: int | None = None, body: str = ""):
        super().__init__(message)
        self.status = status
        self.body = body


def load_dotenv(path: Path | None = None) -> None:
    """อ่านไฟล์ .env แบบง่าย ๆ (KEY=value) เข้า os.environ ถ้ายังไม่ถูกตั้งไว้"""
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_api_key() -> str:
    load_dotenv()
    key = os.environ.get("SEC_API_KEY", "").strip()
    if not key:
        raise SecApiError(
            "ไม่พบ SEC_API_KEY — สมัครและขอ key ได้ที่ https://secopendata.sec.or.th/ "
            "แล้วใส่ไว้ในไฟล์ fund_dashboard/.env เป็น SEC_API_KEY=xxxxx"
        )
    return key


def _ttl_for(path: str) -> int:
    for prefix, ttl in sorted(TTL_BY_PREFIX.items(), key=lambda kv: -len(kv[0])):
        if path.startswith(prefix):
            return ttl
    return DEFAULT_TTL


def _cache_path(path: str, params: dict[str, Any], namespace: str = "") -> Path:
    raw = json.dumps([namespace, path, sorted(params.items())], ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return HTTP_CACHE_DIR / f"{digest}.json"


class SecClient:
    """เรียก SEC Open Data API พร้อม cache บน disk และ retry อัตโนมัติ"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        use_cache: bool = True,
        timeout: int = 60,
        max_retries: int = 4,
        min_interval: float = 0.12,
        backend: str | None = None,
    ):
        load_dotenv()
        self.api_key = api_key or get_api_key()
        self.base_url = (base_url or os.environ.get("SEC_API_BASE_URL", BASE_URL)).rstrip("/")
        self.backend = backend or os.environ.get("SEC_BACKEND", "python")
        if self.backend not in ("python", "sec-go"):
            raise SecApiError("SEC_BACKEND ต้องเป็น python หรือ sec-go")
        self.bridge = os.environ.get("SEC_GO_BINARY", str(ROOT.parent / "bin" / "sec-bridge"))
        if self.backend == "sec-go":
            self._verify_bridge()
        self.use_cache = use_cache
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.min_interval = min_interval
        self._last_call = 0.0
        self._throttle_lock = threading.Lock()
        self.last_response: dict[str, Any] = {}
        self._cache_namespace = self.base_url + ":" + hashlib.sha256(self.api_key.encode()).hexdigest()
        if use_cache:
            HTTP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- HTTP ----------
    def _throttle(self) -> None:
        with self._throttle_lock:
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()

    def _verify_bridge(self) -> None:
        lock = json.loads((ROOT.parent / "tools/sec-bridge/sec-go.lock.json").read_text())
        try:
            result = subprocess.run([self.bridge, "--version"], capture_output=True, text=True, timeout=10, check=True)
            version = json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            raise SecApiError("เรียก sec-bridge ไม่ได้ — build tools/sec-bridge ตาม README ก่อน") from exc
        if version.get("module") != lock["module"] or version.get("version") != lock["version"]:
            raise SecApiError("sec-bridge ไม่ตรงกับ sec-go.lock.json — ต้อง rebuild เวอร์ชันที่ตรึงไว้")

    def _transport(self, path: str, params: dict[str, Any]) -> tuple[int, str, bytes, str]:
        if self.backend == "sec-go":
            env = dict(os.environ, SEC_API_KEY=self.api_key, SEC_API_BASE_URL=self.base_url)
            request = {"path": path, "params": {k: str(v) for k, v in params.items() if v not in (None, "")},
                       "timeout_seconds": self.timeout}
            try:
                result = subprocess.run([self.bridge], input=json.dumps(request), capture_output=True,
                                        text=True, timeout=self.timeout + 5, env=env, check=True)
                response = json.loads(result.stdout)
                if response.get("transport_error"):
                    raise urllib.error.URLError("sec-go transport failed")
                return (int(response["status"]), response.get("content_type", ""),
                        response.get("body", "").encode(), response.get("retry_after", ""))
            except (OSError, subprocess.SubprocessError, ValueError, KeyError) as exc:
                raise SecApiError("sec-bridge ทำงานไม่สำเร็จ (ไม่แสดง stderr เพื่อป้องกันข้อมูลลับ)") from exc
        query = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v not in (None, "")}, safe=","
        )
        url = f"{self.base_url}{path}" + (f"?{query}" if query else "")
        req = urllib.request.Request(
            url,
            headers={
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Accept": "application/json",
                "User-Agent": "thai-fund-dashboard/1.0 (+python-stdlib)",
            },
        )

        try:
            response = urllib.request.urlopen(req, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            response = exc
        with response as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read(), resp.headers.get("Retry-After", "")

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        if path not in ENDPOINTS.values():
            raise SecApiError("ไม่รองรับ SEC endpoint นี้")
        delay = 2.0
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            retry_after = ""
            try:
                status, content_type, raw, retry_after = self._transport(path, params)
                # Log metadata only: never response bodies, request headers or keys.
                media_type = content_type.split(";", 1)[0].strip().lower()
                safe_type = media_type if media_type in ("application/json", "text/html", "text/plain", "") else "other"
                self.last_response = {"path": path, "status": status, "content_type": safe_type, "bytes": len(raw)}
                if status == 204:
                    return {"items": [], "next_cursor": ""}
                if status in (401, 403):
                    raise SecApiError(
                        f"SEC API ปฏิเสธการเข้าถึง ({status}) — ตรวจสอบ API Key และการ subscribe product กองทุน", status)
                if status != 200:
                    last_error = SecApiError(f"SEC API HTTP {status} ที่ {path}", status)
                    if status not in (408, 421, 429, 500, 502, 503, 504):
                        raise last_error
                else:
                    detail = f"HTTP {status}, Content-Type={safe_type or 'missing'}, bytes={len(raw)} ที่ {path}"
                    if not raw.strip():
                        raise SecApiError(f"SEC ส่ง body ว่างโดยไม่ใช่ HTTP 204 ({detail})", status)
                    if media_type and media_type != "application/json" and not media_type.endswith("+json"):
                        raise SecApiError(f"SEC ส่งคำตอบที่ไม่ใช่ JSON ({detail})", status)
                    try:
                        payload = json.loads(raw.decode("utf-8-sig"))
                    except (UnicodeError, ValueError) as exc:
                        raise SecApiError(f"SEC ส่ง JSON ไม่สมบูรณ์ ({detail})", status) from exc
                    return validate_page(payload, path)
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                last_error = SecApiError(f"เชื่อมต่อ SEC API ไม่สำเร็จที่ {path} — network/timeout")
            if attempt < self.max_retries - 1:
                wait = min(float(retry_after), 60) if retry_after.isdigit() else delay
                time.sleep(max(wait, delay))
                delay *= 2
        raise last_error or SecApiError(f"เรียก {path} ไม่สำเร็จ")

    # ---------- public ----------
    def get(self, path: str, params: dict[str, Any] | None = None, ttl: int | None = None) -> dict[str, Any]:
        """ยิง 1 request (1 หน้า) พร้อม cache"""
        params = dict(params or {})
        ttl = _ttl_for(path) if ttl is None else ttl
        cache_file = _cache_path(path, params, self._cache_namespace)
        if self.use_cache and cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                if time.time() - cached.get("fetched_at", 0) < ttl:
                    return validate_page(cached["payload"], path)
            except (json.JSONDecodeError, KeyError, OSError, SecApiError):
                pass

        payload = self._request(path, params)
        if self.use_cache:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=HTTP_CACHE_DIR, delete=False) as fh:
                json.dump({"fetched_at": time.time(), "payload": payload}, fh, ensure_ascii=False)
                tmp = Path(fh.name)
            try:
                tmp.replace(cache_file)
            finally:
                tmp.unlink(missing_ok=True)
        return payload

    def iter_items(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        page_size: int = MAX_PAGE_SIZE,
        max_pages: int = 1000,
        ttl: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """ไล่อ่านทุกหน้าด้วย cursor pagination (next_cursor = "" คือหมดแล้ว)"""
        params = dict(params or {})
        params["page_size"] = min(max(int(page_size), 1), MAX_PAGE_SIZE)
        cursor = ""
        seen: set[str] = set()
        for _ in range(max_pages):
            page_params = dict(params)
            if cursor:
                page_params["next_cursor"] = cursor
            payload = self.get(path, page_params, ttl=ttl)
            items = payload.get("items") or []
            for item in items:
                yield item
            cursor = (payload.get("next_cursor") or "").strip()
            if not cursor:
                return
            if cursor in seen:
                raise SecApiError(f"SEC ส่ง cursor ซ้ำที่ {path} — หยุดเพื่อป้องกันข้อมูลซ้ำ")
            seen.add(cursor)
        raise SecApiError(f"อ่านข้อมูลไม่ครบที่ {path}: เกิน max_pages={max_pages}")

    def fetch_all(self, path: str, params: dict[str, Any] | None = None, **kwargs) -> list[dict[str, Any]]:
        return list(self.iter_items(path, params, **kwargs))


def validate_page(payload: Any, path: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or "items" not in payload:
        raise SecApiError(f"SEC JSON schema ไม่ตรงที่ {path}: ต้องมี items")
    items = payload["items"]
    cursor = payload.get("next_cursor") or ""
    if not isinstance(items, list) or any(not isinstance(row, dict) for row in items) or not isinstance(cursor, str):
        raise SecApiError(f"SEC JSON schema ไม่ตรงที่ {path}: items/next_cursor ผิดชนิด")
    return dict(payload, next_cursor=cursor)


# ---------- endpoint helper (ชื่ออ่านง่าย = จำง่ายเวลานำไปต่อยอด) ----------
ENDPOINTS = {
    "amcs": "/v2/fund/general-info/amcs",
    "profiles": "/v2/fund/general-info/profiles",
    "specifications": "/v2/fund/general-info/specifications",
    "mutual_fund_fees": "/v2/fund/general-info/mutual-fund-fees",
    "involve_parties": "/v2/fund/general-info/involve-parties",
    "factsheet_urls": "/v2/fund/factsheet/urls",
    "ipos": "/v2/fund/factsheet/ipos",
    "redemption_minimums": "/v2/fund/factsheet/subscription-redemption-minimums",
    "redemption_periods": "/v2/fund/factsheet/subscription-redemption-periods",
    "benchmarks": "/v2/fund/factsheet/benchmarks",
    "risk_spectrum": "/v2/fund/factsheet/risk-spectrum",
    "statistics": "/v2/fund/factsheet/statistics",
    "dividend_policy": "/v2/fund/factsheet/dividend-policy",
    "fees": "/v2/fund/factsheet/fees",
    "performance": "/v2/fund/factsheet/performance",
    "asset_allocation": "/v2/fund/factsheet/asset-allocation",
    "top5_holdings": "/v2/fund/factsheet/top5-holdings",
    "nav": "/v2/fund/daily-info/nav",
    "dividend_history": "/v2/fund/daily-info/dividend-history",
}
