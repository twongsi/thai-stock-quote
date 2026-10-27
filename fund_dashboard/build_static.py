"""สร้างเว็บแบบ static (ไฟล์ JSON + หน้าเว็บ) สำหรับ deploy ขึ้น GitHub Pages

แนวคิด: ให้ GitHub Actions เป็นคนดึงข้อมูลจาก SEC API (API Key เก็บใน GitHub Secrets)
แล้ว build ข้อมูลเป็นไฟล์ JSON ไว้ใน site/data/ — หน้าเว็บที่ Pages เสิร์ฟจะอ่านจากไฟล์เหล่านี้
ไม่มีการเรียก SEC API จากเบราว์เซอร์ จึงไม่ต้องเปิด key ให้ใครเห็น และไม่ติดปัญหา CORS

    python3 build_static.py                      # ใช้ watchlist.txt + API จริง
    python3 build_static.py --demo               # ใช้ข้อมูลจำลอง (ไว้ลอง flow ก่อน)
    python3 build_static.py --funds my.txt --out ../site --years 5
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import fund_service
import metrics
from sec_api import SecApiError, SecClient, load_dotenv

ROOT = Path(__file__).resolve().parent
STATIC_SRC = ROOT / "static"

# หน้าต่างเวลาที่หน้าเว็บใช้ในตารางเปรียบเทียบ (ต้องคำนวณไว้ล่วงหน้า เพราะ static ไม่มี backend)
WINDOWS = {"3M": 91, "6M": 182, "1Y": 365, "3Y": 365 * 3, "5Y": 365 * 5}


def slugify(code: str) -> str:
    """SCBNDQ(A) -> SCBNDQ_A_  (ให้เป็นชื่อไฟล์ที่ปลอดภัยบนทุกระบบ)"""
    return re.sub(r"[^A-Z0-9._-]", "_", code.upper())


def read_watchlist(path: Path) -> list[str]:
    codes = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if line:
            codes.append(line)
    return codes


def window_stats(history: list[dict], risk_free: float) -> dict:
    """คำนวณผลตอบแทน/ความเสี่ยงของแต่ละหน้าต่างเวลาไว้ล่วงหน้า"""
    rows = [(row["d"], row["nav"]) for row in history]
    series = metrics.clean_series(rows)
    if len(series) < 2:
        return {}
    end_date = series[-1][0]
    out = {}
    for name, days in WINDOWS.items():
        window = metrics.slice_since(series, end_date - timedelta(days=days))
        if len(window) < 2 or window[0][1] <= 0:
            continue
        total = window[-1][1] / window[0][1] - 1.0
        span = (window[-1][0] - window[0][0]).days
        risk = metrics.risk_metrics(window, risk_free)
        out[name] = {
            "return": total,
            "annualized": metrics.annualize(total, span) if span > 400 else None,
            "start_date": window[0][0].isoformat(),
            "end_date": window[-1][0].isoformat(),
            "volatility": risk.get("volatility"),
            "max_drawdown": risk.get("max_drawdown"),
            "sharpe": risk.get("sharpe"),
        }
    return out


def trim_history(history: list[dict]) -> list[dict]:
    """เก็บเฉพาะ วันที่ + NAV (ฟิลด์อื่นหน้าเว็บไม่ได้ใช้) ลดขนาดไฟล์ราว 60%"""
    return [{"d": row["d"], "nav": round(row["nav"], 4)} for row in history]


def build(client, codes: list[str], out_dir: Path, years: int, risk_free: float, demo: bool) -> int:
    data_dir = out_dir / "data"
    fund_dir = data_dir / "fund"
    fund_dir.mkdir(parents=True, exist_ok=True)

    # คัดลอกหน้าเว็บชุดเดียวกับที่ใช้ตอนรันในเครื่อง
    for name in ("styles.css", "app.js"):
        shutil.copy2(STATIC_SRC / name, out_dir / name)
    # ติดธงไว้ว่าเป็นเว็บ static หน้าเว็บจะได้อ่าน data/*.json ตรง ๆ โดยไม่ต้องลองเรียก /api ก่อน
    html = (STATIC_SRC / "index.html").read_text(encoding="utf-8").replace("<body>", '<body data-mode="static">', 1)
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")   # กัน GitHub Pages ข้ามไฟล์ที่ขึ้นต้นด้วย _

    index: list[dict] = []
    built_by_proj: dict[str, list[str]] = {}
    failures: list[tuple[str, str]] = []
    bundles: dict[str, dict] = {}

    for code in codes:
        started = time.monotonic()
        try:
            bundle = fund_service.build_fund_bundle(client, code, years=years, risk_free=risk_free)
        except SecApiError as exc:
            failures.append((code, str(exc)))
            print(f"  ✗ {code}: {exc}", file=sys.stderr)
            continue

        display = bundle["class_name"] if bundle["class_name"] not in ("", "main", "-", None) else bundle["code"]
        bundle["windows"] = window_stats(bundle["history"], risk_free)
        bundle["history"] = trim_history(bundle["history"])
        bundle["display_code"] = display
        bundles[display] = bundle
        built_by_proj.setdefault(bundle["proj_id"], []).append(display)

        index.append({
            "code": bundle["code"],
            "display_code": display,
            "class_name": bundle["class_name"],
            "proj_id": bundle["proj_id"],
            "name_th": bundle["general"]["name_th"],
            "name_en": bundle["general"]["name_en"],
            "amc_th": bundle["general"]["amc_th"],
            "policy": bundle["general"]["policy_desc"],
            "nav": bundle["latest_nav"]["nav"],
            "nav_date": bundle["latest_nav"]["nav_date"],
            "classes": [],                 # เติมทีหลังเมื่อรู้ว่ากองนี้ build class ไหนบ้าง
            "file": f"data/fund/{slugify(display)}.json",
        })
        print(f"  ✓ {display:<16} {len(bundle['history']):>5} วัน  "
              f"NAV {bundle['latest_nav']['nav']}  ({time.monotonic() - started:.1f}s)")

    # ปุ่มเลือกชนิดหน่วยลงทุน ให้โชว์เฉพาะ class ที่มีไฟล์จริง มิฉะนั้นกดแล้วจะ 404
    for entry in index:
        entry["classes"] = built_by_proj.get(entry["proj_id"], [])
    for display, bundle in bundles.items():
        bundle["classes"] = built_by_proj.get(bundle["proj_id"], [])
        path = fund_dir / f"{slugify(display)}.json"
        path.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    meta = {
        "static": True,
        "demo": demo,
        "generated_at": date.today().isoformat(),
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "history_years": years,
        "risk_free_rate": risk_free,
        "default_code": index[0]["display_code"] if index else "",
        "fund_count": len(index),
        "windows": list(WINDOWS),
        "failures": [{"code": c, "error": e} for c, e in failures],
        "source": "SEC Open Data API (https://secopendata.sec.or.th/)",
    }
    (data_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    (data_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    write_summary(out_dir, meta, index, failures)

    total_bytes = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
    print(f"\nเขียนไฟล์ลง {out_dir} — {len(index)} กองทุน, รวม {total_bytes / 1024:.0f} KB")
    if failures:
        print(f"มี {len(failures)} กองที่ build ไม่สำเร็จ: " + ", ".join(c for c, _ in failures))
    return 0 if index else 1


def write_summary(out_dir: Path, meta: dict, index: list[dict], failures: list[tuple[str, str]]) -> None:
    """สรุปผลเป็น markdown ให้ GitHub Actions เอาไปแปะใน job summary"""
    lines = [
        "### Thai Fund Dashboard",
        "",
        f"- ข้อมูล: {'จำลอง (ยังไม่ได้ใส่ SEC_API_KEY)' if meta['demo'] else 'จริงจาก SEC Open Data API'}",
        f"- อัปเดตเมื่อ: {meta['generated_at_utc']} UTC",
        f"- NAV ย้อนหลัง: {meta['history_years']} ปี",
        f"- กองทุนที่ build สำเร็จ: {len(index)} กอง",
        "",
        "| รหัส | ชื่อกองทุน | NAV ล่าสุด | วันที่ |",
        "| --- | --- | ---: | --- |",
    ]
    for entry in index:
        lines.append(f"| {entry['display_code']} | {entry['name_th']} | {entry.get('nav', '')} | {entry.get('nav_date', '')} |")
    if failures:
        lines += ["", "**กองที่ build ไม่สำเร็จ**", ""]
        lines += [f"- `{code}` — {error}" for code, error in failures]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="build เว็บ static สำหรับ GitHub Pages")
    parser.add_argument("--out", default=str(ROOT.parent / "site"), help="โฟลเดอร์ปลายทาง (ค่าเริ่มต้น ./site)")
    parser.add_argument("--funds", default=str(ROOT / "watchlist.txt"), help="ไฟล์รายชื่อกองทุน")
    parser.add_argument("--code", action="append", help="ระบุกองทุนเพิ่มทีละกอง (ใช้ซ้ำได้)")
    parser.add_argument("--years", type=int, default=5, help="จำนวนปีของ NAV ย้อนหลัง")
    parser.add_argument("--demo", action="store_true", help="ใช้ข้อมูลจำลองแทนการเรียก API จริง")
    args = parser.parse_args()

    load_dotenv()
    codes = list(args.code or [])
    watchlist = Path(args.funds)
    if watchlist.exists():
        codes = read_watchlist(watchlist) + codes
    if not codes:
        print(f"ไม่พบรายชื่อกองทุน — สร้างไฟล์ {watchlist} หรือใช้ --code SCBNDQ", file=sys.stderr)
        return 1

    if args.demo:
        from demo_data import DemoClient

        client = DemoClient()
        print("⚠️  โหมดสาธิต: ข้อมูลที่ build เป็นข้อมูลจำลอง ไม่ใช่ข้อมูลจริงของกองทุน")
    else:
        try:
            client = SecClient()
        except SecApiError as exc:
            print(f"{exc}", file=sys.stderr)
            return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"build {len(codes)} กองทุน → {out_dir}")
    try:
        risk_free = float(os.environ.get("RISK_FREE_RATE", metrics.DEFAULT_RISK_FREE))
    except ValueError:
        risk_free = metrics.DEFAULT_RISK_FREE
    return build(client, codes, out_dir, args.years, risk_free, args.demo)


if __name__ == "__main__":
    sys.exit(main())
