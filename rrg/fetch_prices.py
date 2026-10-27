"""ดึงราคาปิดปรับปรุง (adjusted close) จาก Yahoo Finance สำหรับทำ RRG
ใช้ได้กับ ETF / หุ้น US, หุ้นไทย (.BK), ดัชนี (^SET.BK, ^GSPC) ฯลฯ
ไม่ต้องติดตั้ง library เพิ่ม — ใช้ได้ทั้งเครื่องตัวเองและ Google Colab

ตัวอย่าง:
  python fetch_prices.py --bench TDEX.BK --tickers PTT.BK AOT.BK CPALL.BK --interval 1wk --out set.csv
แล้วนำไฟล์ CSV ไปอัปโหลดในหน้า RRG Studio (คอลัมน์แรกหลัง Date = benchmark)
"""
import argparse, csv, json, ssl, os, time, urllib.request, urllib.parse
from datetime import datetime, timezone

def _ctx():
    ca = os.environ.get("SSL_CERT_FILE") or ("/root/.ccr/ca-bundle.crt" if os.path.exists("/root/.ccr/ca-bundle.crt") else None)
    return ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()

def fetch(symbol, interval="1wk", rng="5y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}"
           f"?range={rng}&interval={interval}&events=div,split&includeAdjustedClose=true")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, context=_ctx(), timeout=30) as r:
                res = json.load(r)["chart"]["result"][0]
            break
        except Exception:
            if attempt == 3: raise
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
    return out, res["meta"]

def table(bench, tickers, interval, rng):
    series, metas = {}, {}
    for s in [bench] + tickers:
        series[s], metas[s] = fetch(s, interval, rng)
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
    import urllib.parse
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", required=True)
    ap.add_argument("--tickers", nargs="+", required=True)
    ap.add_argument("--interval", default="1wk", choices=["1d", "1wk"])
    ap.add_argument("--range", default="5y")
    ap.add_argument("--out", default="prices.csv")
    a = ap.parse_args()
    rows, _ = table(a.bench, a.tickers, a.interval, a.range)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["Date", a.bench] + a.tickers)
        for d, r in rows: w.writerow([d] + ["" if v is None else f"{v:.4f}" for v in r])
    print(f"wrote {a.out}: {len(rows)} rows x {len(a.tickers)+1} symbols")
