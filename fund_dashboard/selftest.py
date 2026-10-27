"""ทดสอบการดึงข้อมูลกองทุนจาก SEC Open Data API

    python3 selftest.py                  # ทดสอบกับ API จริง (ต้องมี SEC_API_KEY ใน .env)
    python3 selftest.py K-ATECH          # ระบุกองทุนที่จะใช้ทดสอบ
    python3 selftest.py --demo           # ทดสอบ pipeline ด้วยข้อมูลจำลอง (ไม่ต้องใช้ key)
    python3 selftest.py --spec           # ตรวจว่า endpoint/พารามิเตอร์/ฟิลด์ที่โค้ดใช้ ยังตรงกับสเปกของ SEC

สคริปต์นี้ไล่ยิงทุก endpoint ที่ dashboard ใช้ แล้วรายงานว่า endpoint ไหนได้ข้อมูล
endpoint ไหนว่าง และ endpoint ไหน error พร้อมเวลาที่ใช้ — เอาไว้เช็กว่า API Key ใช้ได้จริง
และเช็กว่า SEC เปลี่ยนโครงสร้างข้อมูลหรือยัง
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import date, timedelta

import fund_service
import metrics
from sec_api import ENDPOINTS, SecApiError, SecClient, load_dotenv

SPEC_URL = "https://raw.githubusercontent.com/Sitthinut/sec-open-data-api-spec/main/spec/categories/fund.json"

OK = "ผ่าน"
EMPTY = "ว่าง"
FAIL = "ไม่ผ่าน"

# ฟิลด์ที่ dashboard อ่านจริงจากแต่ละ endpoint (ใช้ตรวจกับสเปกของ SEC ด้วย)
USED_FIELDS = {
    "profiles": ["proj_id", "proj_abbr_name", "proj_name_th", "proj_name_en", "comp_name_th",
                 "comp_name_en", "fund_status", "policy_desc", "investment_policy_desc",
                 "management_style", "regis_date", "init_date", "feederfund_master_fund",
                 "feederfund_country", "exchange_rate_protection_policy", "fund_class_name",
                 "fund_class_detail", "fund_class_tax_incentive_type", "fund_class_isin_code"],
    "nav": ["proj_id", "fund_class_name", "nav_date", "net_asset", "last_val",
            "sell_price", "buy_price", "sell_swap_price", "buy_swap_price"],
    "performance": ["proj_id", "fund_class_name", "end_date", "performance_type_desc",
                    "reference_period", "performance_value"],
    "statistics": ["proj_id", "end_date", "sharpe_ratio", "beta", "alpha", "maximum_drawdown",
                   "tracking_error", "portfolio_turnover_ratio", "recovering_period"],
    "risk_spectrum": ["proj_id", "risk_spectrum", "risk_spectrum_desc"],
    "benchmarks": ["proj_id", "benchmark", "benchmark_remark"],
    "fees": ["proj_id", "fee_type_desc", "rate", "actual_value", "fee_other_desc"],
    "mutual_fund_fees": ["proj_id", "fee_type_desc", "rate", "rate_unit"],
    "dividend_policy": ["proj_id", "dividend_policy"],
    "asset_allocation": ["proj_id", "asset_name", "asset_ratio"],
    "top5_holdings": ["proj_id", "asset_name", "asset_ratio"],
    "redemption_minimums": ["proj_id", "minimum_sub_ipo", "minimum_sub", "minimum_redempt", "lowbal_val"],
    "redemption_periods": ["proj_id", "type", "period", "settlement_period"],
    "specifications": ["proj_id", "spec_code", "spec_desc"],
    "factsheet_urls": ["proj_id", "amc_url_factsheet", "pdf_factsheet", "as_of_date"],
    "dividend_history": ["proj_id", "book_close_date", "dividend_date", "dividend_value"],
}

# พารามิเตอร์ที่โค้ดส่งไปจริง
USED_PARAMS = {
    "profiles": ["project_info", "fund_status", "page_size", "next_cursor"],
    "nav": ["proj_id", "start_nav_date", "end_nav_date", "fund_class_name", "page_size", "next_cursor"],
    "performance": ["proj_id", "latest", "fund_class_name", "page_size", "next_cursor"],
    "statistics": ["proj_id", "latest", "fund_class_name", "page_size", "next_cursor"],
    "fees": ["proj_id", "latest", "fund_class_name", "page_size", "next_cursor"],
    "dividend_policy": ["proj_id", "latest", "fund_class_name", "page_size", "next_cursor"],
    "risk_spectrum": ["proj_id", "latest", "page_size", "next_cursor"],
    "benchmarks": ["proj_id", "latest", "page_size", "next_cursor"],
    "asset_allocation": ["proj_id", "latest", "page_size", "next_cursor"],
    "top5_holdings": ["proj_id", "latest", "page_size", "next_cursor"],
    "redemption_minimums": ["proj_id", "latest", "fund_class_name", "page_size", "next_cursor"],
    "redemption_periods": ["proj_id", "latest", "fund_class_name", "page_size", "next_cursor"],
    "mutual_fund_fees": ["proj_id", "page_size", "next_cursor"],
    "specifications": ["proj_id", "page_size", "next_cursor"],
    "factsheet_urls": ["proj_id", "page_size", "next_cursor"],
    "dividend_history": ["proj_id", "page_size", "next_cursor"],
}


def line(char: str = "─", width: int = 78) -> None:
    print(char * width)


def result(name: str, status: str, detail: str = "", seconds: float | None = None) -> None:
    mark = {OK: "✓", EMPTY: "○", FAIL: "✗"}[status]
    timing = f"{seconds * 1000:7.0f} ms" if seconds is not None else " " * 10
    print(f" {mark} {name:<26} {timing}  {detail}")


# ---------------------------------------------------------------- ทดสอบกับ API
def probe_endpoints(client, proj_id: str, class_name: str | None) -> dict[str, str]:
    """ยิงทุก endpoint ที่ dashboard ใช้ แล้วรายงานผลทีละตัว"""
    start_nav = (date.today() - timedelta(days=400)).isoformat()
    cases: list[tuple[str, dict]] = [
        ("nav", {"proj_id": proj_id, "start_nav_date": start_nav, "fund_class_name": class_name}),
        ("performance", {"proj_id": proj_id, "latest": "true", "fund_class_name": class_name}),
        ("statistics", {"proj_id": proj_id, "latest": "true", "fund_class_name": class_name}),
        ("risk_spectrum", {"proj_id": proj_id, "latest": "true"}),
        ("benchmarks", {"proj_id": proj_id, "latest": "true"}),
        ("fees", {"proj_id": proj_id, "latest": "true", "fund_class_name": class_name}),
        ("mutual_fund_fees", {"proj_id": proj_id}),
        ("dividend_policy", {"proj_id": proj_id, "latest": "true", "fund_class_name": class_name}),
        ("asset_allocation", {"proj_id": proj_id, "latest": "true"}),
        ("top5_holdings", {"proj_id": proj_id, "latest": "true"}),
        ("redemption_minimums", {"proj_id": proj_id, "latest": "true", "fund_class_name": class_name}),
        ("redemption_periods", {"proj_id": proj_id, "latest": "true", "fund_class_name": class_name}),
        ("specifications", {"proj_id": proj_id}),
        ("factsheet_urls", {"proj_id": proj_id}),
        ("dividend_history", {"proj_id": proj_id}),
    ]
    statuses: dict[str, str] = {}
    for key, params in cases:
        params = {k: v for k, v in params.items() if v not in (None, "")}
        started = time.monotonic()
        try:
            rows = client.fetch_all(ENDPOINTS[key], params, max_pages=400)
            elapsed = time.monotonic() - started
            if rows:
                unexpected = [f for f in USED_FIELDS.get(key, []) if f not in rows[0]]
                detail = f"{len(rows):>5} แถว"
                if unexpected:
                    detail += f"  ⚠ ไม่พบฟิลด์: {', '.join(unexpected[:4])}"
                    statuses[key] = FAIL
                    result(key, FAIL, detail, elapsed)
                    continue
                statuses[key] = OK
                result(key, OK, detail, elapsed)
            else:
                statuses[key] = EMPTY
                result(key, EMPTY, "ไม่มีข้อมูล (กองนี้อาจไม่มีข้อมูลส่วนนี้)", elapsed)
        except SecApiError as exc:
            statuses[key] = FAIL
            result(key, FAIL, str(exc)[:70], time.monotonic() - started)
    return statuses


def check_bundle(client, code: str, years: int) -> bool:
    """สร้างข้อมูลชุดเต็มของกองทุน แล้วตรวจความสมเหตุสมผลของตัวเลข"""
    started = time.monotonic()
    bundle = fund_service.build_fund_bundle(client, code, years=years)
    elapsed = time.monotonic() - started

    history = bundle["history"]
    summary = bundle["summary"]
    print()
    print(f" กองทุน  : {bundle['code']}  ({bundle['class_name']})  {bundle['proj_id']}")
    print(f" ชื่อ     : {bundle['general']['name_th']}")
    print(f" บลจ.     : {bundle['general']['amc_th']}")
    print(f" NAV      : {bundle['latest_nav']['nav']}  ณ {bundle['latest_nav']['nav_date']}"
          f"   (ขนาดกองทุน {bundle['latest_nav']['net_asset']:,.0f} บาท)"
          if bundle["latest_nav"]["net_asset"] else f" NAV      : {bundle['latest_nav']['nav']}")
    print(f" ข้อมูล NAV: {len(history):,} วัน  ({summary.get('first_date')} → {summary.get('latest_date')})"
          f"  ใช้เวลาประกอบข้อมูล {elapsed:.1f} วินาที")
    print()
    print(" ผลตอบแทน : " + "  ".join(
        f"{p['period']} {p['return'] * 100:+.2f}%" if p.get("return") is not None else f"{p['period']} —"
        for p in summary.get("periods", [])
    ))
    risk = summary.get("risk_1y", {})
    if risk.get("available"):
        print(f" ความเสี่ยง 1 ปี : ผันผวน {risk['volatility'] * 100:.2f}%  "
              f"maxDD {risk['max_drawdown'] * 100:.2f}%  Sharpe {risk['sharpe']:.2f}")
    print(f" factsheet : ผลการดำเนินงาน {len(bundle['sec_performance']['rows'])} ช่วง · "
          f"ทรัพย์สิน {len(bundle['allocation'])} ประเภท · top5 {len(bundle['top5'])} รายการ · "
          f"ค่าธรรมเนียม {len(bundle['fees'])} รายการ")
    print()

    # ---- ตรวจความสมเหตุสมผล ----
    checks: list[tuple[str, bool, str]] = []
    checks.append(("มีข้อมูล NAV", len(history) > 20, f"{len(history)} วัน"))
    checks.append(("NAV เป็นบวกทุกวัน", all(row["nav"] > 0 for row in history), ""))
    dates = [row["d"] for row in history]
    checks.append(("วันที่เรียงจากเก่าไปใหม่", dates == sorted(dates), ""))
    checks.append(("ไม่มีวันที่ซ้ำ", len(dates) == len(set(dates)), ""))
    checks.append(("มีชื่อกองทุนและ บลจ.", bool(bundle["general"]["name_th"] and bundle["general"]["amc_th"]), ""))
    one_year = next((p for p in summary.get("periods", []) if p["period"] == "1Y"), {})
    if one_year.get("return") is not None:
        checks.append(("ผลตอบแทน 1 ปี อยู่ในช่วงที่เป็นไปได้ (-90% ถึง +300%)",
                       -0.9 < one_year["return"] < 3.0, f"{one_year['return'] * 100:+.2f}%"))
    if risk.get("available"):
        checks.append(("ความผันผวนอยู่ในช่วงที่เป็นไปได้ (0–150%)", 0 <= risk["volatility"] < 1.5,
                       f"{risk['volatility'] * 100:.2f}%"))
        checks.append(("max drawdown ไม่เป็นบวก", risk["max_drawdown"] <= 0, ""))

    ok = True
    for name, passed, detail in checks:
        result(name, OK if passed else FAIL, detail)
        ok = ok and passed
    return ok


def run_api_test(code: str, years: int, demo: bool) -> int:
    if demo:
        from demo_data import DemoClient

        client = DemoClient()
        print(" โหมด: สาธิต (ข้อมูลจำลอง — ไม่ได้เรียก SEC API จริง)")
    else:
        load_dotenv()
        try:
            client = SecClient()
        except SecApiError as exc:
            print(f" ✗ {exc}")
            print("   ถ้ายังไม่มี key ลองโหมดจำลองก่อนได้:  python3 selftest.py --demo")
            return 1
        print(f" โหมด: เรียก SEC Open Data API จริง (key ลงท้ายด้วย …{client.api_key[-4:]})")

    line()
    print(" 1) ทดสอบการเชื่อมต่อและ API Key")
    line()
    started = time.monotonic()
    try:
        amcs = client.fetch_all(ENDPOINTS["amcs"], {}, max_pages=1)
        result("เชื่อมต่อ + ยืนยัน key", OK, f"รายชื่อ บลจ. {len(amcs)} รายการ", time.monotonic() - started)
    except SecApiError as exc:
        result("เชื่อมต่อ + ยืนยัน key", FAIL, str(exc)[:90], time.monotonic() - started)
        if exc.status in (401, 403):
            print("\n   แก้: ตรวจว่า key ถูกต้อง และ subscribe product กลุ่ม Fund แล้วที่ https://secopendata.sec.or.th/")
        return 1

    print()
    line()
    print(f" 2) ค้นหากองทุน '{code}'")
    line()
    started = time.monotonic()
    try:
        fund = fund_service.resolve_fund(client, code)
    except SecApiError as exc:
        result("ค้นหากองทุน", FAIL, str(exc)[:90], time.monotonic() - started)
        return 1
    result("ค้นหากองทุน", OK,
           f"{fund['code']} → {fund['proj_id']} · {len(fund['classes'])} ชนิดหน่วยลงทุน",
           time.monotonic() - started)
    class_name = fund.get("matched_class") or (fund["classes"][0] if fund["classes"] else None)

    print()
    line()
    print(" 3) ทดสอบทีละ endpoint")
    line()
    statuses = probe_endpoints(client, fund["proj_id"], class_name)

    print()
    line()
    print(" 4) ประกอบข้อมูลชุดเต็ม + ตรวจความสมเหตุสมผลของตัวเลข")
    line()
    try:
        sane = check_bundle(client, code, years)
    except SecApiError as exc:
        result("ประกอบข้อมูล", FAIL, str(exc)[:90])
        return 1

    failed = [k for k, v in statuses.items() if v == FAIL]
    empty = [k for k, v in statuses.items() if v == EMPTY]
    line("═")
    print(f" สรุป: endpoint ผ่าน {len(statuses) - len(failed) - len(empty)}/{len(statuses)}"
          + (f" · ว่าง {len(empty)} ({', '.join(empty)})" if empty else "")
          + (f" · ไม่ผ่าน {len(failed)} ({', '.join(failed)})" if failed else ""))
    print(" ตัวเลขในชุดข้อมูล: " + ("สมเหตุสมผลทั้งหมด" if sane else "มีข้อที่ไม่ผ่าน — ดูรายการด้านบน"))
    line("═")
    return 0 if (not failed and sane) else 1


# ---------------------------------------------------------------- ตรวจกับสเปก
def run_spec_check(spec_path: str | None) -> int:
    """เทียบ endpoint / query parameter / ชื่อฟิลด์ ที่โค้ดใช้ กับสเปกของ SEC

    ใช้ตอน SEC ประกาศเปลี่ยน API: ถ้ามีอะไรหายไปจะฟ้องตรงนี้ก่อนที่ dashboard จะพัง
    """
    if spec_path:
        spec = json.loads(open(spec_path, encoding="utf-8").read())
        source = spec_path
    else:
        with urllib.request.urlopen(SPEC_URL, timeout=60) as resp:
            spec = json.loads(resp.read().decode("utf-8"))
        source = SPEC_URL

    by_endpoint = {a["endpoint"]: a for a in spec.get("apiLists", []) if a.get("endpoint")}
    print(f" สเปกอ้างอิง: {source}")
    print(f" endpoint ในสเปก: {len(by_endpoint)} รายการ")
    line()

    problems = 0
    for key, path in ENDPOINTS.items():
        spec_api = by_endpoint.get(path)
        if not spec_api:
            result(f"{key} ({path})", FAIL, "ไม่พบ endpoint นี้ในสเปก")
            problems += 1
            continue

        issues = []
        spec_params = {p["name"] for p in spec_api.get("queryParameters", [])}
        missing_params = [p for p in USED_PARAMS.get(key, []) if p not in spec_params]
        if missing_params:
            issues.append(f"พารามิเตอร์ที่ไม่มีในสเปก: {', '.join(missing_params)}")

        dictionary = spec_api.get("responses", {}).get("dataDictionary", []) or []
        spec_fields = {f["fieldName"].replace("items[].", "") for f in dictionary}
        example = (spec_api.get("responses", {}).get("dataExample", {}) or {}).get("items") or []
        if example:
            spec_fields |= set(example[0].keys())
        missing_fields = [f for f in USED_FIELDS.get(key, []) if f not in spec_fields]
        if missing_fields:
            issues.append(f"ฟิลด์ที่ไม่มีในสเปก: {', '.join(missing_fields)}")

        if issues:
            result(key, FAIL, " · ".join(issues)[:120])
            problems += 1
        else:
            used = len(USED_FIELDS.get(key, []))
            result(key, OK, f"ตรงกับสเปก ({used} ฟิลด์ที่ใช้)" if used else "ตรงกับสเปก")

    line("═")
    print(" สรุป: " + ("ทุก endpoint/ฟิลด์ที่โค้ดใช้ ยังตรงกับสเปกของ SEC"
                       if not problems else f"มี {problems} จุดที่ไม่ตรงกับสเปก — ต้องแก้โค้ดก่อนใช้งานจริง"))
    line("═")
    return 0 if not problems else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="ทดสอบการดึงข้อมูลกองทุนจาก SEC Open Data API")
    parser.add_argument("code", nargs="?", default="K-ATECH", help="ชื่อย่อกองทุนที่ใช้ทดสอบ (ค่าเริ่มต้น K-ATECH)")
    parser.add_argument("--demo", action="store_true", help="ทดสอบด้วยข้อมูลจำลอง ไม่ต้องใช้ API Key")
    parser.add_argument("--years", type=int, default=3, help="จำนวนปีของ NAV ที่ดึงมาทดสอบ (ค่าเริ่มต้น 3)")
    parser.add_argument("--spec", action="store_true", help="ตรวจโครงสร้าง endpoint/ฟิลด์กับสเปกของ SEC")
    parser.add_argument("--spec-file", help="ใช้ไฟล์สเปกในเครื่องแทนการดาวน์โหลด")
    args = parser.parse_args()

    print()
    line("═")
    print(" ทดสอบการดึงข้อมูลกองทุน — Thai Fund Dashboard")
    line("═")

    if args.spec or args.spec_file:
        return run_spec_check(args.spec_file)
    return run_api_test(args.code, args.years, args.demo)


if __name__ == "__main__":
    sys.exit(main())
