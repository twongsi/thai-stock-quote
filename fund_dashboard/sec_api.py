"""Client สำหรับ SEC Open Data API (secopendata.sec.or.th) เวอร์ชัน v2

ใช้เฉพาะ standard library ของ Python เท่านั้น ไม่ต้อง pip install อะไรเพิ่ม

เอกสาร API: https://secopendata.sec.or.th/  (ต้องสมัครและขอ API Key ก่อน)
ทุก request ต้องแนบ header `Ocp-Apim-Subscription-Key: <API KEY ของเรา>`
"""

from __future__ import annotations

import hashlib
import json
import os
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


def _cache_path(path: str, params: dict[str, Any]) -> Path:
    raw = json.dumps([path, sorted(params.items())], ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
    return HTTP_CACHE_DIR / f"{digest}.json"


class SecClient:
    """เรียก SEC Open Data API พร้อม cache บน disk และ retry อัตโนมัติ"""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = BASE_URL,
        use_cache: bool = True,
        timeout: int = 60,
        max_retries: int = 4,
        min_interval: float = 0.12,
    ):
        self.api_key = api_key or get_api_key()
        self.base_url = base_url.rstrip("/")
        self.use_cache = use_cache
        self.timeout = timeout
        self.max_retries = max_retries
        self.min_interval = min_interval
        self._last_call = 0.0
        if use_cache:
            HTTP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- HTTP ----------
    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
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

        delay = 2.0
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            self._throttle()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", "replace")[:500]
                # 401/403 = key ผิดหรือยังไม่ได้ subscribe -> ไม่ต้อง retry
                if exc.code in (401, 403):
                    raise SecApiError(
                        f"SEC API ปฏิเสธการเข้าถึง ({exc.code}) — ตรวจสอบ API Key และการ subscribe product กองทุน",
                        exc.code,
                        body,
                    ) from exc
                if exc.code == 404:
                    raise SecApiError(f"ไม่พบ endpoint {path} ({exc.code})", exc.code, body) from exc
                last_error = SecApiError(f"SEC API error {exc.code} ที่ {path}", exc.code, body)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = SecApiError(f"เชื่อมต่อ SEC API ไม่สำเร็จ: {exc}")
            if attempt < self.max_retries - 1:
                time.sleep(delay)
                delay *= 2
        raise last_error or SecApiError(f"เรียก {path} ไม่สำเร็จ")

    # ---------- public ----------
    def get(self, path: str, params: dict[str, Any] | None = None, ttl: int | None = None) -> dict[str, Any]:
        """ยิง 1 request (1 หน้า) พร้อม cache"""
        params = dict(params or {})
        ttl = _ttl_for(path) if ttl is None else ttl
        cache_file = _cache_path(path, params)
        if self.use_cache and cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                if time.time() - cached.get("fetched_at", 0) < ttl:
                    return cached["payload"]
            except (json.JSONDecodeError, KeyError, OSError):
                pass

        payload = self._request(path, params)
        if self.use_cache:
            tmp = cache_file.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"fetched_at": time.time(), "payload": payload}, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(cache_file)
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
        for _ in range(max_pages):
            page_params = dict(params)
            if cursor:
                page_params["next_cursor"] = cursor
            payload = self.get(path, page_params, ttl=ttl)
            items = payload.get("items") or []
            for item in items:
                yield item
            cursor = (payload.get("next_cursor") or "").strip()
            if not cursor or not items:
                return

    def fetch_all(self, path: str, params: dict[str, Any] | None = None, **kwargs) -> list[dict[str, Any]]:
        return list(self.iter_items(path, params, **kwargs))


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
