"""Minimal live diagnostic. Prints response metadata, never keys or bodies."""

import json
import sys

from sec_api import ENDPOINTS, SecApiError, SecClient


def main() -> int:
    try:
        client = SecClient(use_cache=False, timeout=20, max_retries=2)
    except SecApiError as exc:
        print(str(exc))
        return 1
    failed = False
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
