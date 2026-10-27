"""ดึงราคาปิดปรับปรุง (adjusted close) จาก Yahoo Finance สำหรับทำ RRG
ใช้ได้กับ ETF / หุ้น US, หุ้นไทย (.BK), ดัชนี (^SET.BK, ^GSPC) ฯลฯ
ไม่ต้องติดตั้ง library เพิ่ม — ใช้ได้ทั้งเครื่องตัวเองและ Google Colab

ตัวอย่าง:
  python fetch_prices.py --bench TDEX.BK --tickers PTT.BK AOT.BK CPALL.BK --interval 1wk --out set.csv
แล้วนำไฟล์ CSV ไปอัปโหลดในหน้า RRG Studio (คอลัมน์แรกหลัง Date = benchmark)
"""
import argparse, csv, json, ssl, os, time, urllib.error, urllib.request, urllib.parse
from datetime import datetime, timezone

def _ctx():
    ca = os.environ.get("SSL_CERT_FILE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else None)
    return ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()

# Corporate actions that Yahoo does not carry into Adj Close: (symbol, first date of the
# new series, new shares per old share). Prices before that date are divided by the ratio
# so the series is in new-share terms and the week of the swap shows the real return.
KNOWN_ADJUSTMENTS = [
    ("TRUE.BK", "2023-02-27", 0.60477),  # TRUE–DTAC amalgamation: 1 old TRUE → 0.60477 new TRUE
]

def adjust(symbol, prices):
    for sym, start, ratio in KNOWN_ADJUSTMENTS:
        if sym == symbol:
            prices = {d: (p / ratio if d < start else p) for d, p in prices.items()}
    return prices

def fetch(symbol, interval="1wk", rng="5y"):
    q = (f"/v8/finance/chart/{urllib.parse.quote(symbol)}"
         f"?range={rng}&interval={interval}&events=div,split&includeAdjustedClose=true")
    for attempt in range(5):
        host = "query1" if attempt % 2 == 0 else "query2"  # สลับ host เมื่อโดนจำกัดการเรียก
        req = urllib.request.Request(f"https://{host}.finance.yahoo.com{q}", headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req, context=_ctx(), timeout=30) as r:
                res = json.load(r)["chart"]["result"][0]
            break
        except urllib.error.HTTPError as e:
            if e.code == 404 or attempt == 4: raise
            time.sleep(2 ** attempt)
        except Exception:
            if attempt == 4: raise
            time.sleep(2 ** attempt)
    ts = res["timestamp"]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose") or res["indicators"]["quote"][0]["close"]
    tz = res["meta"].get("gmtoffset", 0)
    out = {}
    for t, p in zip(ts, adj):
        if p is None: continue
        d = datetime.fromtimestamp(t + tz, tz=timezone.utc).strftime("%Y-%m-%d")
        out[d] = p
    if interval == "1wk":
        # Yahoo ใส่แท่งของสัปดาห์ปัจจุบันซ้ำเป็นอีกแถว: รวมเป็น 1 แถวต่อสัปดาห์ (ใช้ราคาล่าสุด)
        wk = {}
        for d in sorted(out):
            key = datetime.strptime(d, "%Y-%m-%d").isocalendar()[:2]
            first = wk.get(key, (d, None))[0]
            wk[key] = (first, out[d])
        out = dict(wk.values())
    return adjust(symbol, out), res["meta"]

def table(bench, tickers, interval, rng):
    """ตารางราคาเรียงตามวันของ benchmark; ตัวที่ดึงไม่ได้จะถูกข้าม (ดู `skipped` ที่คืนใน metas)"""
    series, metas = {}, {"skipped": []}
    series[bench], metas[bench] = fetch(bench, interval, rng)
    ok = []
    for s in tickers:
        try:
            series[s], metas[s] = fetch(s, interval, rng); ok.append(s)
        except Exception as e:
            print(f"skip {s}: {e}"); metas["skipped"].append(s)
    tickers = ok
    dates = sorted(set(series[bench]))
    # forward-fill ราคาที่ขาดในวันที่ benchmark มีข้อมูล
    rows, last = [], {}
    for d in dates:
        row = []
        for s in [bench] + tickers:
            if d in series[s]: last[s] = series[s][d]
            row.append(last.get(s))
        rows.append((d, row))
    return rows, metas

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--tickers", nargs="+", required=True)
    ap.add_argument("--interval", default="1wk", choices=["1d", "1wk"])
    ap.add_argument("--range", default="5y")
    ap.add_argument("--out", default="prices.csv")
    a = ap.parse_args()
    rows, metas = table(a.bench, a.tickers, a.interval, a.range)
    tickers = [t for t in a.tickers if t not in metas["skipped"]]
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Date", a.bench] + tickers)
        for d, r in rows: w.writerow([d] + ["" if v is None else f"{v:.4f}" for v in r])
    print(f"wrote {a.out}: {len(rows)} rows x {len(tickers)+1} symbols")
