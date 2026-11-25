"""One read interface for cached weekly Thai stock bars and daily SEC fund NAV."""

from __future__ import annotations

import csv
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path

import fund_service
from sec_api import SecApiError

DATA_ROOT = Path(__file__).resolve().parent.parent / "data"


def stock_history(symbol: str, data_root: Path = DATA_ROOT) -> dict:
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9&._-]{0,39}", symbol):
        raise SecApiError("รหัสหุ้นไม่ถูกต้อง", 400)
    paths = [data_root / "market/prices" / f"{symbol}.csv", data_root / f"{symbol}.csv"]
    file = next((p for p in paths if p.is_file()), None)
    if file is None:
        raise SecApiError(f"ไม่มีข้อมูลหุ้น {symbol} ในชุดข้อมูลที่ดาวน์โหลด", 404)
    points = {}
    with file.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            try:
                day = date.fromisoformat(row["Date"][:10]).isoformat()
                price = float(row["Close"])
                if math.isfinite(price) and price > 0:
                    points[day] = {"date": day, "price": price}
            except (KeyError, TypeError, ValueError):
                continue
    if not points:
        raise SecApiError(f"ไม่มีราคาที่ใช้ได้สำหรับ {symbol}", 404)
    return {
        "asset_type": "stock", "symbol": symbol, "price_type": "close",
        "currency": "THB", "interval": "1wk", "date_semantics": "bar_start_date",
        "source": "Yahoo Finance (repository CSV)", "is_realtime": False, "is_demo": False,
        "history": [points[key] for key in sorted(points)],
    }


def fund_history(client, symbol: str, years: int, class_name: str | None, demo: bool) -> dict:
    fund = fund_service.resolve_fund(client, symbol)
    rows = fund_service.fetch_nav_series(client, fund["proj_id"], None, years)
    preferred = class_name or fund.get("matched_class")
    chosen, _ = fund_service._pick_class([], rows, preferred)
    points = {}
    for row in rows:
        if (row.get("fund_class_name") or "") != (chosen or ""):
            continue
        try:
            day = date.fromisoformat(str(row["nav_date"])[:10]).isoformat()
            value = float(row["last_val"])
            if math.isfinite(value) and value > 0:
                points[day] = {"date": day, "price": value}
        except (KeyError, TypeError, ValueError):
            continue
    if not points:
        raise SecApiError("ไม่มี NAV ของชนิดหน่วยลงทุนที่เลือก", 404)
    return {
        "asset_type": "fund", "symbol": fund["code"], "proj_id": fund["proj_id"],
        "class_name": chosen, "price_type": "nav", "currency": None,
        "currency_note": "NAV endpoint does not identify currency; verify the share-class factsheet",
        "interval": "1d", "date_semantics": "nav_date",
        "source": "demo" if demo else "SEC Open Data API", "is_realtime": False, "is_demo": demo,
        "history": [points[key] for key in sorted(points)],
    }


def get_history(params: dict, client_factory, demo: bool = False) -> dict:
    kind = params.get("asset_type", "").strip().lower()
    symbol = params.get("symbol", "").strip()
    if not symbol or kind not in ("stock", "fund"):
        raise SecApiError("ระบุ asset_type=stock|fund และ symbol", 400)
    try:
        years = int(params.get("years") or 5)
        if not 1 <= years <= 20:
            raise ValueError
        start = date.fromisoformat(params["start"]) if params.get("start") else None
        end = date.fromisoformat(params["end"]) if params.get("end") else None
        if start and end and start > end:
            raise ValueError
    except ValueError as exc:
        raise SecApiError("years ต้องเป็น 1–20 และวันที่ start/end ต้องเป็น YYYY-MM-DD ตามลำดับ", 400) from exc
    result = stock_history(symbol) if kind == "stock" else fund_history(
        client_factory(), symbol, years, params.get("class") or None, demo)
    result["history"] = [point for point in result["history"]
                         if (not start or point["date"] >= start.isoformat())
                         and (not end or point["date"] <= end.isoformat())]
    if not result["history"]:
        raise SecApiError("ไม่มีข้อมูลในช่วงวันที่เลือก", 404)
    latest = result["history"][-1]
    result.update(price=latest["price"], as_of=latest["date"],
                  served_at=datetime.now(timezone.utc).isoformat(),
                  age_days=(date.today() - date.fromisoformat(latest["date"])).days)
    return result


def get_quote(params: dict, client_factory, demo: bool = False) -> dict:
    result = get_history(params, client_factory, demo)
    result.pop("history")
    return result
