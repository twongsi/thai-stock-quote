"""Minimal live diagnostic. Prints response metadata, never keys or bodies."""

import json
import sys
import argparse

from sec_api import ENDPOINTS, SecApiError, SecClient


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true", help="แสดงเฉพาะรหัสกองทุน/ชนิดหน่วยลงทุนสาธารณะเพื่อแก้ watchlist")
    args = parser.parse_args()
    try:
        client = SecClient(use_cache=False, timeout=20, max_retries=2)
    except SecApiError as exc:
        print(str(exc))
        return 1
    failed = False
    if args.discover:
        for query in ("K-ATECH", "SCBSET50", "KFGBRAND", "KF-GBRAND", "M0317_2559", "ES-GOLDS"):
            try:
                page = client.get(ENDPOINTS["profiles"], {"project_info": query, "page_size": 100})
                identifiers = [{k: row.get(k) for k in ("proj_id", "proj_abbr_name", "fund_class_name", "fund_status")}
                               for row in page["items"]]
                print(json.dumps({"query": query, "identifiers": identifiers, "more_pages": bool(page.get("next_cursor"))}, ensure_ascii=False))
            except SecApiError as exc:
                print(json.dumps({"query": query, "error": str(exc)}, ensure_ascii=False))
                failed = True
        return 1 if failed else 0
    for endpoint, params in [("amcs", {}), ("profiles", {}), ("profiles", {"project_info": "SCBNDQ"})]:
        try:
            page = client.get(ENDPOINTS[endpoint], dict(params, page_size=1))
            print(json.dumps(dict(client.last_response, backend=client.backend, rows=len(page["items"])), ensure_ascii=False))
            if not params and not page["items"]:
                failed = True
        except SecApiError as exc:
            print(json.dumps(dict(client.last_response, error=str(exc)), ensure_ascii=False))
            failed = True
            if exc.status in (401, 403):
                break
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
