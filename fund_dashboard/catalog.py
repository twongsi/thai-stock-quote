"""สร้าง "สมุดรายชื่อกองทุนไทยทั้งหมด" ไว้ในเครื่อง (cache/catalog.json)

ทำไมต้องมี
  - ช่องค้นหาจะ suggest ได้ทันทีโดยไม่ต้องยิง API ทุกตัวอักษร
  - ปุ่ม "รายชื่อกองทุน" เอาไว้ไล่ดูตาม บลจ. / ประเภทนโยบายการลงทุน
  - ใช้จัดกลุ่ม peer เพื่อเทียบผลตอบแทนกับ "กองทุนกลุ่มเดียวกัน"

วิธีใช้
    python3 catalog.py --build          # ดึงรายชื่อกองทุนทั้งหมด (ใช้เวลาสักพัก)
    python3 catalog.py --build --all    # รวมกองที่เลิกแล้วด้วย
    python3 catalog.py --peers          # คำนวณผลตอบแทนเฉลี่ยของแต่ละกลุ่มนโยบาย
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import metrics
from sec_api import CACHE_DIR, ENDPOINTS, SecApiError, SecClient

CATALOG_PATH = CACHE_DIR / "catalog.json"
PEERS_PATH = CACHE_DIR / "peers.json"
ACTIVE_STATUS = {"Registered", "IPO"}


def build_catalog(client: SecClient, active_only: bool = True, verbose: bool = True) -> dict:
    """ดึง /v2/fund/general-info/profiles ทุกหน้า แล้วยุบหลาย class ให้เหลือกองละ 1 รายการ"""
    funds: dict[str, dict] = {}
    started = time.time()
    count = 0

    statuses = sorted(ACTIVE_STATUS) if active_only else [None]
    for status in statuses:
        params = {"fund_status": status} if status else {}
        for row in client.iter_items(ENDPOINTS["profiles"], params, max_pages=2000):
            count += 1
            proj_id = row.get("proj_id")
            if not proj_id:
                continue
            if active_only and row.get("fund_status") not in ACTIVE_STATUS:
                continue
            fund = funds.setdefault(
                proj_id,
                {
                    "proj_id": proj_id,
                    "code": row.get("proj_abbr_name") or "",
                    "name_th": row.get("proj_name_th") or "",
                    "name_en": row.get("proj_name_en") or "",
                    "amc_th": row.get("comp_name_th") or "",
                    "amc_en": row.get("comp_name_en") or "",
                    "unique_id": row.get("unique_id") or "",
                    "status": row.get("fund_status") or "",
                    "policy": row.get("policy_desc") or "",
                    "regis_date": row.get("regis_date") or "",
                    "classes": [],
                },
            )
            class_name = row.get("fund_class_name") or ""
            if class_name and class_name not in fund["classes"]:
                fund["classes"].append(class_name)
            if verbose and count % 2000 == 0:
                print(f"  ... อ่านแล้ว {count:,} แถว / {len(funds):,} กองทุน", file=sys.stderr)

    catalog = {
        "generated_at": date.today().isoformat(),
        "active_only": active_only,
        "count": len(funds),
        "funds": sorted(funds.values(), key=lambda f: (f["code"] or "zzz", f["proj_id"])),
    }
    CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CATALOG_PATH.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
    if verbose:
        print(
            f"บันทึก {len(funds):,} กองทุน ({count:,} แถวรวม class) ลง {CATALOG_PATH} "
            f"ใช้เวลา {time.time() - started:.0f} วินาที",
            file=sys.stderr,
        )
    return catalog


def load_catalog(path: Path = CATALOG_PATH) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def search_catalog(catalog: dict, query: str, limit: int = 15) -> list[dict]:
    """ค้นจากไฟล์ในเครื่อง: ให้คะแนนรหัสกองทุนก่อน แล้วค่อยชื่อกองทุน/บลจ."""
    needle = (query or "").strip().upper()
    if len(needle) < 1:
        return []
    scored: list[tuple[tuple, dict]] = []
    for fund in catalog.get("funds", []):
        code = (fund.get("code") or "").upper()
        classes = [c.upper() for c in fund.get("classes", [])]
        name = f"{fund.get('name_th','')} {fund.get('name_en','')}".upper()
        amc = f"{fund.get('amc_th','')} {fund.get('amc_en','')}".upper()
        if code == needle or needle in classes:
            rank = 0
        elif code.startswith(needle) or any(c.startswith(needle) for c in classes):
            rank = 1
        elif needle in code or any(needle in c for c in classes):
            rank = 2
        elif needle in name:
            rank = 3
        elif needle in amc:
            rank = 4
        else:
            continue
        scored.append(((rank, len(code), code), fund))
    scored.sort(key=lambda item: item[0])
    return [fund for _, fund in scored[:limit]]


# ---------------------------------------------------------------- peer group
def build_peer_stats(
    client: SecClient,
    sample_per_group: int = 40,
    years: int = 5,
    verbose: bool = True,
) -> dict:
    """ค่าเฉลี่ยผลตอบแทนของกองทุน "กลุ่มเดียวกัน" (จัดกลุ่มตาม policy_desc ของ SEC)

    ดึง NAV ของกองทุนตัวอย่างในแต่ละกลุ่ม (ค่าเริ่มต้นกลุ่มละ 40 กอง) แล้วหาค่ามัธยฐาน
    ของผลตอบแทนแต่ละช่วงเวลา เพื่อใช้เป็นเส้นเปรียบเทียบบน dashboard
    """
    catalog = load_catalog()
    if not catalog:
        raise SecApiError("ยังไม่มี catalog — รัน `python3 catalog.py --build` ก่อน")

    groups: dict[str, list[dict]] = {}
    for fund in catalog["funds"]:
        policy = (fund.get("policy") or "ไม่ระบุ").strip()
        groups.setdefault(policy, []).append(fund)

    start = (date.today() - timedelta(days=365 * years + 7)).isoformat()
    out: dict[str, dict] = {}
    for policy, members in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        sample = members[:sample_per_group]
        buckets: dict[str, list[float]] = {}
        used = 0
        for fund in sample:
            try:
                rows = client.fetch_all(
                    ENDPOINTS["nav"],
                    {"proj_id": fund["proj_id"], "start_nav_date": start},
                    max_pages=400,
                )
            except SecApiError:
                continue
            by_class: dict[str, list[tuple[str, float]]] = {}
            for row in rows:
                by_class.setdefault(row.get("fund_class_name") or "main", []).append(
                    (row.get("nav_date"), row.get("last_val"))
                )
            if not by_class:
                continue
            series = metrics.clean_series(max(by_class.values(), key=len))
            if len(series) < 30:
                continue
            used += 1
            for label, days in metrics.PERIODS:
                result = metrics.period_return(series, label, days)
                if result.get("available") and result.get("return") is not None:
                    value = result["annualized"] if result.get("annualized") is not None else result["return"]
                    buckets.setdefault(label, []).append(value)
        if used >= 3:
            out[policy] = {
                "sample_size": used,
                "median": {k: sorted(v)[len(v) // 2] for k, v in buckets.items() if v},
            }
            if verbose:
                print(f"  {policy}: {used} กอง", file=sys.stderr)

    payload = {"generated_at": date.today().isoformat(), "years": years, "groups": out}
    PEERS_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    if verbose:
        print(f"บันทึกค่าเฉลี่ยกลุ่ม {len(out)} กลุ่ม ลง {PEERS_PATH}", file=sys.stderr)
    return payload


def load_peers(path: Path = PEERS_PATH) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="สร้าง catalog / peer stats ของกองทุนไทยจาก SEC Open API")
    parser.add_argument("--build", action="store_true", help="ดึงรายชื่อกองทุนทั้งหมด")
    parser.add_argument("--all", action="store_true", help="รวมกองทุนที่เลิกโครงการแล้ว")
    parser.add_argument("--peers", action="store_true", help="คำนวณผลตอบแทนเฉลี่ยรายกลุ่มนโยบาย")
    parser.add_argument("--sample", type=int, default=40, help="จำนวนกองตัวอย่างต่อกลุ่ม (ค่าเริ่มต้น 40)")
    args = parser.parse_args()

    if not (args.build or args.peers):
        parser.print_help()
        return

    client = SecClient()
    if args.build:
        build_catalog(client, active_only=not args.all)
    if args.peers:
        build_peer_stats(client, sample_per_group=args.sample)


if __name__ == "__main__":
    main()
