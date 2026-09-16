"""ประกอบข้อมูลจาก SEC Open Data API หลาย endpoint ให้เป็นก้อนเดียวที่ dashboard ใช้ได้เลย

ไอเดียหลัก
  1) ค้นกองทุนด้วย "ชื่อย่อ" (เช่น K-ATECH, SCBNDQ) ผ่าน profiles?project_info=<คำค้น>
     ซึ่ง SEC ค้นแบบ partial match ให้จาก proj_id / proj_name_th / proj_name_en / proj_abbr_name
  2) ได้ proj_id แล้วจึงดึง NAV รายวัน + factsheet ที่เหลือ
  3) คำนวณผลตอบแทน/ความเสี่ยงเองจาก NAV จริง (metrics.py) ควบคู่กับตัวเลขที่ SEC ให้มา
"""

from __future__ import annotations

import os
import re
from datetime import date, timedelta

import metrics
from sec_api import ENDPOINTS, SecApiError

ACTIVE_STATUS = {"REGISTERED", "IPO"}
TOTAL_FEE_KEYWORDS = ("รวมค่าใช้จ่าย", "ค่าใช้จ่ายรวม", "ค่าธรรมเนียมทั้งหมด", "รวมทั้งสิ้น", "total expense")
DEFAULT_HISTORY_YEARS = int(os.environ.get("SEC_HISTORY_YEARS", "5"))

RISK_SPECTRUM_LABELS = {
    "RS1": "เสี่ยงต่ำ — ตราสารตลาดเงินในประเทศ",
    "RS2": "เสี่ยงต่ำ — ตราสารตลาดเงินที่ลงทุนต่างประเทศบางส่วน",
    "RS3": "เสี่ยงปานกลางค่อนข้างต่ำ — ตราสารหนี้ภาครัฐ",
    "RS4": "เสี่ยงปานกลางค่อนข้างต่ำ — ตราสารหนี้ทั่วไป",
    "RS5": "เสี่ยงปานกลางค่อนข้างสูง — ผสม",
    "RS6": "เสี่ยงสูง — ตราสารทุน",
    "RS7": "เสี่ยงสูง — หมวดอุตสาหกรรมเดียว",
    "RS8": "เสี่ยงสูงมาก — สินทรัพย์ทางเลือก",
}
POLICY_LABEL = {"Y": "มีนโยบายจ่ายเงินปันผล", "N": "ไม่จ่ายเงินปันผล"}


def _norm(value) -> str:
    return re.sub(r"[\s]+", "", str(value or "")).upper()


def _clean_html(text: str, limit: int = 1200) -> str:
    text = re.sub(r"<br\s*/?>", "\n", str(text or ""))
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _to_float(value) -> float | None:
    try:
        text = str(value).replace(",", "").replace("%", "").strip()
        return float(text) if text else None
    except (TypeError, ValueError):
        return None


def _total_fee(fees: list[dict], amc_fees: list[dict]) -> dict | None:
    """หา "ค่าธรรมเนียมรวมทั้งหมด" ต่อปี — ลองจาก factsheet ก่อน แล้วค่อยจากข้อมูล บลจ."""
    for source in (fees, amc_fees):
        for row in source:
            label = str(row.get("fee_type_desc") or "")
            if any(k in label.lower() or k in label for k in TOTAL_FEE_KEYWORDS):
                value = _to_float(row.get("actual_value")) or _to_float(row.get("rate"))
                if value is not None:
                    return {"label": label, "value": value}
    # ไม่มีแถว "รวม" -> บวกค่าธรรมเนียมที่เก็บจากกองทุน (management + trustee + registrar)
    total = 0.0
    found = False
    for row in amc_fees:
        label = str(row.get("fee_type_desc") or "")
        unit = str(row.get("rate_unit") or "")
        if "ต่อปี" not in unit and "ต่อปี" not in label:
            continue
        value = _to_float(row.get("rate"))
        if value is None:
            continue
        total += value
        found = True
    return {"label": "รวมค่าธรรมเนียมที่เรียกเก็บจากกองทุน (ประมาณ)", "value": total} if found else None


def _subscription_info(minimums: list[dict], periods: list[dict]) -> dict:
    """ซื้อขั้นต่ำ / ขายคืนขั้นต่ำ / ช่วงเวลาทำรายการ / ระยะเวลารับเงินค่าขายคืน"""
    row = minimums[0] if minimums else {}
    subscription = next((p for p in periods if str(p.get("type") or "").lower() == "subscription"), {})
    redemption = next((p for p in periods if str(p.get("type") or "").lower() != "subscription"), {})
    return {
        "minimum_sub_ipo": _to_float(row.get("minimum_sub_ipo")),
        "minimum_sub": _to_float(row.get("minimum_sub")),
        "minimum_redempt": _to_float(row.get("minimum_redempt")),
        "minimum_balance": _to_float(row.get("lowbal_val")),
        "currency": (row.get("minimum_sub_cur") or "THB").strip(),
        "subscription_period": (subscription.get("period") or "").strip(),
        "redemption_period": (redemption.get("period") or "").strip(),
        "settlement_period": (redemption.get("settlement_period") or subscription.get("settlement_period") or "").strip(),
        "as_of": row.get("end_date") or subscription.get("end_date") or "",
    }


def _highlights(fees: list[dict], amc_fees: list[dict], minimums: list[dict], periods: list[dict]) -> dict:
    """4 ตัวเลขสั้น ๆ ที่โชว์ใต้ชื่อกองทุน"""
    info = _subscription_info(minimums, periods)
    return {
        "total_fee": _total_fee(fees, amc_fees),
        "minimum_sub": info["minimum_sub"] if info["minimum_sub"] is not None else info["minimum_sub_ipo"],
        "settlement": info["settlement_period"],
        "redemption_period": info["redemption_period"],
    }


def peer_reference(peers: dict | None, policy: str) -> dict | None:
    """ดึงค่ามัธยฐานผลตอบแทนของกองทุนกลุ่มเดียวกัน (ถ้าเคยรัน catalog.py --peers ไว้)"""
    if not peers or not policy:
        return None
    group = (peers.get("groups") or {}).get(policy.strip())
    if not group:
        return None
    return {
        "policy": policy.strip(),
        "sample_size": group.get("sample_size"),
        "median": group.get("median", {}),
        "generated_at": peers.get("generated_at"),
    }


# ---------------------------------------------------------------- search
def search_funds(client, query: str, limit: int = 20, active_only: bool = True) -> list[dict]:
    """ค้นกองทุนจากคำค้น แล้วยุบแถวที่เป็นกองเดียวกัน (หลาย class) ให้เหลือรายการเดียว"""
    query = (query or "").strip()
    if len(query) < 2:
        return []

    rows = client.fetch_all(ENDPOINTS["profiles"], {"project_info": query}, max_pages=8)
    grouped: dict[str, dict] = {}
    for row in rows:
        proj_id = row.get("proj_id")
        if not proj_id:
            continue
        status = str(row.get("fund_status") or "").upper()
        if active_only and status not in ACTIVE_STATUS:
            continue
        fund = grouped.setdefault(
            proj_id,
            {
                "proj_id": proj_id,
                "code": row.get("proj_abbr_name") or "",
                "name_th": row.get("proj_name_th") or "",
                "name_en": row.get("proj_name_en") or "",
                "amc_th": row.get("comp_name_th") or "",
                "amc_en": row.get("comp_name_en") or "",
                "status": row.get("fund_status") or "",
                "policy": row.get("policy_desc") or "",
                "classes": [],
            },
        )
        class_name = row.get("fund_class_name") or ""
        if class_name and class_name not in fund["classes"]:
            fund["classes"].append(class_name)

    needle = _norm(query)
    def score(fund: dict) -> tuple:
        code = _norm(fund["code"])
        classes = [_norm(c) for c in fund["classes"]]
        if code == needle or needle in classes:
            rank = 0
        elif code.startswith(needle) or any(c.startswith(needle) for c in classes):
            rank = 1
        elif needle in code:
            rank = 2
        else:
            rank = 3
        return (rank, len(code), fund["code"])

    return sorted(grouped.values(), key=score)[:limit]


def resolve_fund(client, code: str, active_only: bool = True) -> dict:
    """แปลงชื่อย่อกองทุน -> กองทุนที่ตรงที่สุด (พร้อมบอกว่า match กับ class ไหน)"""
    results = search_funds(client, code, limit=30, active_only=active_only)
    if not results and active_only:
        results = search_funds(client, code, limit=30, active_only=False)
    if not results:
        raise SecApiError(f"ไม่พบกองทุนที่ตรงกับ '{code}' — ลองใส่ชื่อย่อ เช่น K-ATECH หรือ SCBNDQ")

    needle = _norm(code)
    best = results[0]
    matched_class = None
    for fund in results:
        if _norm(fund["code"]) == needle:
            best = fund
            break
        for class_name in fund["classes"]:
            if _norm(class_name) == needle:
                best, matched_class = fund, class_name
                break
        if matched_class:
            break
    if matched_class is None:
        for class_name in best["classes"]:
            if _norm(class_name) == needle:
                matched_class = class_name
    best = dict(best)
    best["matched_class"] = matched_class
    return best


# ---------------------------------------------------------------- building blocks
def _latest(client, key: str, proj_id: str, extra: dict | None = None) -> list[dict]:
    """ดึง factsheet ฉบับล่าสุดของกองทุน (latest=true) แบบไม่ให้ error ทำให้ทั้งหน้าพัง"""
    params = {"proj_id": proj_id, "latest": "true"}
    params.update(extra or {})
    try:
        return client.fetch_all(ENDPOINTS[key], params, max_pages=5)
    except SecApiError:
        return []


def fetch_nav_series(client, proj_id: str, fund_class_name: str | None, years: int) -> list[dict]:
    start = (date.today() - timedelta(days=365 * years + 7)).isoformat()
    params = {"proj_id": proj_id, "start_nav_date": start, "end_nav_date": date.today().isoformat()}
    if fund_class_name:
        params["fund_class_name"] = fund_class_name
    return client.fetch_all(ENDPOINTS["nav"], params, max_pages=400)


def _pick_class(profile_rows: list[dict], nav_rows: list[dict], preferred: str | None) -> tuple[str | None, list[str]]:
    """เลือก class ที่จะแสดง: ตามที่ผู้ใช้ค้น > class ที่มี NAV ล่าสุด > main"""
    classes: list[str] = []
    for row in profile_rows:
        name = row.get("fund_class_name") or ""
        if name and name not in classes:
            classes.append(name)
    nav_classes: list[str] = []
    for row in nav_rows:
        name = row.get("fund_class_name") or ""
        if name and name not in nav_classes:
            nav_classes.append(name)
    for name in nav_classes:
        if name not in classes:
            classes.append(name)

    if preferred:
        for name in classes:
            if _norm(name) == _norm(preferred):
                return name, classes
    if nav_classes:
        return nav_classes[0], classes
    return (classes[0] if classes else None), classes


def _performance_table(rows: list[dict]) -> dict:
    """พลิกตารางผลการดำเนินงานของ SEC: แถว = ช่วงเวลา, คอลัมน์ = ประเภทข้อมูล"""
    order: list[str] = []
    columns: list[str] = []
    table: dict[str, dict[str, str]] = {}
    as_of = ""
    for row in rows:
        period = (row.get("reference_period") or "").strip()
        kind = (row.get("performance_type_desc") or "").strip()
        if not period or not kind:
            continue
        as_of = max(as_of, str(row.get("end_date") or ""))
        if period not in table:
            table[period] = {}
            order.append(period)
        if kind not in columns:
            columns.append(kind)
        table[period][kind] = row.get("performance_value")
    return {
        "as_of": as_of,
        "columns": columns,
        "rows": [{"period": p, "values": table[p]} for p in order],
    }


def build_fund_bundle(
    client,
    code: str,
    fund_class_name: str | None = None,
    years: int = DEFAULT_HISTORY_YEARS,
    risk_free: float = metrics.DEFAULT_RISK_FREE,
) -> dict:
    """รวมทุกอย่างของกองทุน 1 กองไว้ใน dict เดียว — dashboard เรียกครั้งเดียวจบ"""
    fund = resolve_fund(client, code)
    proj_id = fund["proj_id"]

    profile_rows = client.fetch_all(ENDPOINTS["profiles"], {"project_info": proj_id}, max_pages=5)
    profile_rows = [r for r in profile_rows if r.get("proj_id") == proj_id] or profile_rows
    nav_rows_all = fetch_nav_series(client, proj_id, None, years)

    preferred = fund_class_name or fund.get("matched_class")
    chosen_class, class_names = _pick_class(profile_rows, nav_rows_all, preferred)

    nav_rows = [r for r in nav_rows_all if (r.get("fund_class_name") or "") == (chosen_class or "")] or nav_rows_all
    nav_rows.sort(key=lambda r: str(r.get("nav_date") or ""))

    base = next((r for r in profile_rows if (r.get("fund_class_name") or "") == (chosen_class or "")), profile_rows[0] if profile_rows else {})

    series_rows = [(r.get("nav_date"), r.get("last_val")) for r in nav_rows]
    summary = metrics.summarize(series_rows, risk_free=risk_free)
    history = [
        {
            "d": str(r.get("nav_date"))[:10],
            "nav": float(r.get("last_val")),
            "net_asset": float(r.get("net_asset")) if r.get("net_asset") not in (None, "") else None,
            "sell": float(r["sell_price"]) if r.get("sell_price") not in (None, "") else None,
            "buy": float(r["buy_price"]) if r.get("buy_price") not in (None, "") else None,
        }
        for r in nav_rows
        if r.get("last_val") not in (None, "") and float(r.get("last_val") or 0) > 0
    ]

    class_extra = {"fund_class_name": chosen_class} if chosen_class else {}
    statistics = _latest(client, "statistics", proj_id, class_extra)
    performance = _latest(client, "performance", proj_id, class_extra)
    fees = _latest(client, "fees", proj_id, class_extra)
    dividend = _latest(client, "dividend_policy", proj_id, class_extra)
    risk_spectrum = _latest(client, "risk_spectrum", proj_id)
    benchmarks = _latest(client, "benchmarks", proj_id)
    allocation = _latest(client, "asset_allocation", proj_id)
    top5 = _latest(client, "top5_holdings", proj_id)
    try:
        urls = client.fetch_all(ENDPOINTS["factsheet_urls"], {"proj_id": proj_id}, max_pages=3)
    except SecApiError:
        urls = []
    try:
        dividend_history = client.fetch_all(
            ENDPOINTS["dividend_history"], {"proj_id": proj_id}, max_pages=5
        )
    except SecApiError:
        dividend_history = []

    minimums = _latest(client, "redemption_minimums", proj_id, class_extra)
    periods = _latest(client, "redemption_periods", proj_id, class_extra)
    try:
        amc_fees = client.fetch_all(
            ENDPOINTS["mutual_fund_fees"], {"proj_id": proj_id}, max_pages=3
        )
    except SecApiError:
        amc_fees = []
    try:
        specifications = client.fetch_all(
            ENDPOINTS["specifications"], {"proj_id": proj_id}, max_pages=3
        )
    except SecApiError:
        specifications = []

    stat = statistics[0] if statistics else {}
    spectrum = risk_spectrum[0] if risk_spectrum else {}
    spectrum_code = str(spectrum.get("risk_spectrum") or "").upper()
    latest_nav_row = nav_rows[-1] if nav_rows else {}

    return {
        "query": code,
        "proj_id": proj_id,
        "code": base.get("proj_abbr_name") or fund["code"],
        "class_name": chosen_class,
        "classes": class_names,
        "general": {
            "name_th": base.get("proj_name_th") or fund["name_th"],
            "name_en": base.get("proj_name_en") or fund["name_en"],
            "amc_th": base.get("comp_name_th") or fund["amc_th"],
            "amc_en": base.get("comp_name_en") or fund["amc_en"],
            "status": base.get("fund_status") or fund["status"],
            "policy_desc": base.get("policy_desc") or "",
            "management_style": base.get("management_style") or "",
            "regis_date": base.get("regis_date") or "",
            "init_date": base.get("init_date") or "",
            "proj_retail_type": base.get("proj_retail_type") or "",
            "proj_term_flag": base.get("proj_term_flag") or "",
            "feeder_master_fund": base.get("feederfund_master_fund") or "",
            "feeder_country": base.get("feederfund_country") or "",
            "fx_policy": base.get("exchange_rate_protection_policy") or "",
            "class_detail": base.get("fund_class_detail") or "",
            "class_description": base.get("fund_class_description") or "",
            "tax_incentive": base.get("fund_class_tax_incentive_type") or "",
            "isin": base.get("fund_class_isin_code") or "",
            "investment_policy": _clean_html(base.get("investment_policy_desc")),
        },
        "latest_nav": {
            "nav_date": str(latest_nav_row.get("nav_date") or "")[:10],
            "nav": summary.get("latest_nav"),
            "previous_nav": summary.get("previous_nav"),
            "daily_change": summary.get("daily_change"),
            "net_asset": latest_nav_row.get("net_asset"),
            "sell_price": latest_nav_row.get("sell_price"),
            "buy_price": latest_nav_row.get("buy_price"),
            "sell_swap_price": latest_nav_row.get("sell_swap_price"),
            "buy_swap_price": latest_nav_row.get("buy_swap_price"),
        },
        "history": history,
        "summary": summary,
        "risk_spectrum": {
            "code": spectrum_code,
            "level": int(spectrum_code[2:]) if spectrum_code[2:].isdigit() else None,
            "label": RISK_SPECTRUM_LABELS.get(spectrum_code, ""),
            "description": spectrum.get("risk_spectrum_desc") or "",
        },
        "sec_statistics": {
            "as_of": stat.get("end_date") or "",
            "sharpe_ratio": stat.get("sharpe_ratio"),
            "beta": stat.get("beta"),
            "alpha": stat.get("alpha"),
            "max_drawdown": stat.get("maximum_drawdown"),
            "tracking_error": stat.get("tracking_error"),
            "portfolio_turnover_ratio": stat.get("portfolio_turnover_ratio"),
            "recovering_period": stat.get("recovering_period"),
            "portfolio_duration_period": stat.get("portfolio_duration_period"),
            "yield_to_maturity": stat.get("yield_to_maturity"),
            "fx_hedging": stat.get("fx_hedging"),
        },
        "sec_performance": _performance_table(performance),
        "benchmarks": [
            {"benchmark": r.get("benchmark"), "remark": r.get("benchmark_remark"), "as_of": r.get("end_date")}
            for r in benchmarks
        ],
        "allocation": sorted(
            [
                {"name": r.get("asset_name"), "ratio": float(r.get("asset_ratio") or 0), "as_of": r.get("end_date")}
                for r in allocation
                if r.get("asset_name")
            ],
            key=lambda x: -x["ratio"],
        ),
        "top5": sorted(
            [
                {"name": r.get("asset_name"), "ratio": float(r.get("asset_ratio") or 0), "as_of": r.get("end_date")}
                for r in top5
                if r.get("asset_name")
            ],
            key=lambda x: -x["ratio"],
        ),
        "highlights": _highlights(fees, amc_fees, minimums, periods),
        "specifications": [
            {"code": r.get("spec_code"), "desc": r.get("spec_desc")}
            for r in specifications
            if r.get("spec_desc")
        ][:6],
        "amc_fees": [
            {
                "type": r.get("fee_type_desc"),
                "rate": r.get("rate"),
                "unit": (r.get("rate_unit") or "").strip(),
                "class_name": r.get("fund_class_name"),
            }
            for r in amc_fees
        ][:20],
        "subscription": _subscription_info(minimums, periods),
        "fees": [
            {
                "type": r.get("fee_type_desc"),
                "rate": r.get("rate"),
                "actual": r.get("actual_value"),
                "remark": _clean_html(r.get("fee_other_desc"), 300),
            }
            for r in fees
        ],
        "dividend_policy": {
            "flag": (dividend[0].get("dividend_policy") if dividend else ""),
            "label": POLICY_LABEL.get(str(dividend[0].get("dividend_policy") or "").upper(), "") if dividend else "",
        },
        "dividend_history": [
            {
                "book_close_date": str(r.get("book_close_date") or "")[:10],
                "dividend_date": str(r.get("dividend_date") or "")[:10],
                "value": r.get("dividend_value"),
            }
            for r in sorted(
                dividend_history,
                key=lambda r: str(r.get("dividend_date") or r.get("book_close_date") or ""),
                reverse=True,
            )[:12]
        ],
        "factsheet_urls": [
            {
                "amc_url": r.get("amc_url_factsheet"),
                "pdf": r.get("pdf_factsheet"),
                "as_of": r.get("as_of_date"),
                "class_name": r.get("fund_class_name"),
            }
            for r in urls
        ][:4],
    }


def build_comparison(
    client,
    codes: list[str],
    years: int = DEFAULT_HISTORY_YEARS,
    window: str = "1Y",
    risk_free: float = metrics.DEFAULT_RISK_FREE,
) -> dict:
    """เทียบหลายกองทุน: ปรับฐาน NAV = 100 ณ วันเริ่มหน้าต่างที่เลือก + ตารางสถิติ"""
    window_days = {"3M": 91, "6M": 182, "YTD": None, "1Y": 365, "3Y": 365 * 3, "5Y": 365 * 5}
    days = window_days.get(window.upper(), 365)

    funds: list[dict] = []
    errors: list[dict] = []
    for code in codes:
        code = code.strip()
        if not code:
            continue
        try:
            fund = resolve_fund(client, code)
            nav_rows = fetch_nav_series(client, fund["proj_id"], fund.get("matched_class"), years)
            if not nav_rows:
                nav_rows = fetch_nav_series(client, fund["proj_id"], None, years)
            chosen = fund.get("matched_class") or (nav_rows[0].get("fund_class_name") if nav_rows else None)
            rows = [
                (r.get("nav_date"), r.get("last_val"))
                for r in nav_rows
                if (r.get("fund_class_name") or "") == (chosen or "")
            ] or [(r.get("nav_date"), r.get("last_val")) for r in nav_rows]
            series = metrics.clean_series(rows)
            if len(series) < 2:
                errors.append({"code": code, "error": "ไม่มีข้อมูล NAV ย้อนหลังพอสำหรับเปรียบเทียบ"})
                continue
            funds.append(
                {
                    "code": fund["code"],
                    "class_name": chosen,
                    "proj_id": fund["proj_id"],
                    "name_th": fund["name_th"],
                    "amc_th": fund["amc_th"],
                    "policy": fund["policy"],
                    "series": series,
                    "rows": rows,
                }
            )
        except SecApiError as exc:
            errors.append({"code": code, "error": str(exc)})

    if not funds:
        return {"window": window, "funds": [], "errors": errors, "start_date": None}

    end_date = max(f["series"][-1][0] for f in funds)
    if days is None:
        start_date = date(end_date.year, 1, 1)
    else:
        start_date = end_date - timedelta(days=days)
    # เริ่มกราฟที่วันที่ทุกกองมีข้อมูลครบ เพื่อไม่ให้กองที่ข้อมูลสั้นกว่าเสียเปรียบ
    common_start = max(f["series"][0][0] for f in funds)
    start_date = max(start_date, common_start)

    out_funds = []
    for fund in funds:
        indexed = metrics.indexed_series(fund["rows"], start=start_date)
        window_series = metrics.slice_since(fund["series"], start_date)
        window_return = None
        if len(window_series) >= 2 and window_series[0][1] > 0:
            window_return = window_series[-1][1] / window_series[0][1] - 1.0
        out_funds.append(
            {
                "code": fund["code"],
                "class_name": fund["class_name"],
                "proj_id": fund["proj_id"],
                "name_th": fund["name_th"],
                "amc_th": fund["amc_th"],
                "policy": fund["policy"],
                "indexed": indexed,
                "window_return": window_return,
                "latest_nav": fund["series"][-1][1],
                "latest_date": fund["series"][-1][0].isoformat(),
                "periods": {
                    p["period"]: {"return": p["return"], "annualized": p.get("annualized")}
                    for p in (metrics.period_return(fund["series"], label, d) for label, d in metrics.PERIODS)
                },
                "risk": metrics.risk_metrics(window_series, risk_free),
            }
        )

    out_funds.sort(key=lambda f: (f["window_return"] is None, -(f["window_return"] or 0)))
    return {
        "window": window.upper(),
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "funds": out_funds,
        "errors": errors,
    }
