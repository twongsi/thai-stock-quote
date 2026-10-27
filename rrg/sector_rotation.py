"""Sector rotation workflow สำหรับหุ้นรายตัว → ดัชนีหมวด → RRG → สัญญาณ → backtest

ขั้นตอน (ตรงกับหัวข้อในโค้ด):
  1. Universe   : รายชื่อหุ้น + หมวด (sector map) + benchmark
  2. Data       : ราคาปิดปรับปรุง (adjusted close) รายสัปดาห์/รายวัน, (ถ้ามี) มูลค่าตลาดสำหรับถ่วงน้ำหนัก
  3. Sector idx : สร้างดัชนีหมวดจากหุ้นสมาชิก  I_t = I_{t-1} · (1 + Σ w_i r_i,t)
  4. Relative   : RS, RS-Ratio, RS-Momentum, excess return, β, correlation, trend filter
  5. Score      : รวมเป็นคะแนนเดียวต่อหมวด แล้วจัดอันดับ
  6. Select     : เลือก top-k หมวด (และหุ้นเด่นในหมวด) — สัญญาณ ณ t ใช้กับผลตอบแทน t+1 เท่านั้น
  7. Backtest   : rebalance ตามรอบ, หักค่าธรรมเนียม, วัด CAGR / Sharpe / MaxDD / IR / turnover

ใช้แค่ pandas + numpy; ดึงข้อมูลด้วย fetch_prices.py (Yahoo Finance)
ตัวอย่าง:
  python sector_rotation.py --preset set --top 3 --rebalance 4 --out results
"""
from __future__ import annotations
import argparse, json, os
import numpy as np
import pandas as pd

# ------------------------------------------------------------------ 1. Universe
SET_SECTORS = {
    "BANK": ["KBANK", "SCB", "BBL", "KTB", "TTB", "KKP", "TISCO"],
    "FIN": ["KTC", "MTC", "SAWAD", "TIDLOR", "AEONTS"],
    "INSUR": ["BLA", "TLI", "TQM"],
    "ENERG": ["PTT", "PTTEP", "GULF", "TOP", "BCP", "OR", "BGRIM", "EGCO", "GPSC", "RATCH", "BANPU", "EA"],
    "PETRO": ["IVL", "PTTGC", "IRPC"],
    "PROP": ["CPN", "LH", "AP", "SPALI", "WHA", "AMATA"],
    "CONMAT": ["SCC", "TOA", "DCC", "TASCO"],
    "COMM": ["CPALL", "CRC", "HMPRO", "BJC", "CPAXT", "GLOBAL"],
    "HELTH": ["BDMS", "BH", "BCH", "CHG"],
    "TOURISM": ["CENTEL", "ERW", "MINT"],
    "TRANS": ["AOT", "BEM", "BTS", "BA"],
    "ICT": ["ADVANC", "TRUE", "JAS"],
    "ETRON": ["DELTA", "KCE", "HANA", "CCET"],
    "FOOD": ["CPF", "TU", "CBG", "OSP", "TFG", "GFPT", "BTG", "M"],
}
PRESETS = {
    "set": {"bench": "TDEX.BK", "suffix": ".BK", "sectors": SET_SECTORS},
}


# ------------------------------------------------------------------ 2. Data
def load_prices(symbols: list[str], bench: str, interval="1wk", rng="10y") -> pd.DataFrame:
    """คืน DataFrame ราคาปิดปรับปรุง: index = วันที่, คอลัมน์ = สัญลักษณ์ (คอลัมน์แรก = benchmark)"""
    from fetch_prices import fetch
    cols = {}
    for s in [bench] + symbols:
        try:
            cols[s] = pd.Series(fetch(s, interval, rng)[0])
        except Exception as e:  # หุ้นที่ดึงไม่ได้ข้ามไป ไม่ทำให้ทั้งระบบล้ม
            print(f"skip {s}: {e}")
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df[df[bench].notna()].ffill(limit=2)


# ------------------------------------------------------------------ 3. Sector index
def sector_index(prices: pd.DataFrame, members: dict[str, list[str]],
                 weights: pd.DataFrame | None = None) -> pd.DataFrame:
    """ดัชนีหมวด  I_t = I_{t-1} · (1 + Σ_i w_i,t-1 · r_i,t)
    - weights=None  → equal weight (w = 1/N ของสมาชิกที่มีข้อมูล)
    - weights=DF    → เช่น market cap ณ ปลายงวดก่อน (cap-weight แบบดัชนีทางการ)
    น้ำหนักใช้ค่า ณ t-1 เพื่อไม่ให้มองอนาคต (no look-ahead)"""
    rets = prices.pct_change(fill_method=None)
    out = {}
    for sec, syms in members.items():
        syms = [s for s in syms if s in rets]
        if not syms:
            continue
        r = rets[syms]
        if weights is None:
            w = r.notna().astype(float)
        else:
            w = weights[syms].shift(1).where(r.notna())
        w = w.div(w.sum(axis=1), axis=0)
        port = (r.fillna(0) * w.fillna(0)).sum(axis=1)
        port[w.sum(axis=1) == 0] = np.nan
        out[sec] = 100 * (1 + port.fillna(0)).cumprod()
    return pd.DataFrame(out)


# ------------------------------------------------------------------ 4. Relative measures
def zscore(s: pd.DataFrame, n: int) -> pd.DataFrame:
    return (s - s.rolling(n).mean()) / s.rolling(n).std()


def rrg(idx: pd.DataFrame, bench: pd.Series, n: int = 14):
    """RS_t        = 100 · I_t / B_t
       RS-Ratio_t  = 100 + z(RS, n)          (ตำแหน่งแนวโน้มเทียบ benchmark)
       RS-Mom_t    = 100 + z(RS-Ratio, n)    (อัตราเปลี่ยนของแนวโน้ม)
       Quadrant    : Leading (≥100, ≥100), Weakening (≥100, <100), Lagging (<100, <100), Improving (<100, ≥100)"""
    rs = 100 * idx.div(bench, axis=0)
    ratio = 100 + zscore(rs, n)
    mom = 100 + zscore(ratio, n)
    quad = pd.DataFrame(np.select(
        [(ratio >= 100) & (mom >= 100), (ratio >= 100) & (mom < 100), (ratio < 100) & (mom < 100)],
        ["Leading", "Weakening", "Lagging"], "Improving"), index=idx.index, columns=idx.columns)
    quad = quad.where(ratio.notna() & mom.notna())
    heading = np.degrees(np.arctan2(mom.diff(), ratio.diff())) % 360  # ทิศของหาง: 0=E, 90=N
    return rs, ratio, mom, quad, heading


def relative_stats(idx: pd.DataFrame, bench: pd.Series, look: int = 52, skip: int = 4):
    """ความสัมพันธ์อื่นที่ใช้ประกอบ:
       Excess return  ER = (1+R_i)/(1+R_B) − 1           (ผลตอบแทนส่วนเกินแบบ geometric)
       Momentum 12-1  M  = P_{t-skip}/P_{t-look} − 1     (Jegadeesh-Titman / Moskowitz-Grinblatt)
       Beta           β  = Cov(r_i, r_B) / Var(r_B)
       Correlation    ρ  = Cov(r_i, r_B) / (σ_i σ_B)
       Trend filter   T  = 1 ถ้า I_t > SMA(I, 40 สัปดาห์)  (≈ 200 วัน)"""
    r, rb = idx.pct_change(fill_method=None), bench.pct_change(fill_method=None)
    rel = idx.div(bench, axis=0)
    er = rel / rel.shift(look) - 1
    mom121 = idx.shift(skip) / idx.shift(look) - 1
    cov = r.rolling(look).cov(rb)
    beta = cov.div(rb.rolling(look).var(), axis=0)
    corr = r.rolling(look).corr(rb)
    trend = (idx > idx.rolling(40).mean()).astype(float).where(idx.rolling(40).count() == 40)
    return {"excess": er, "mom121": mom121, "beta": beta, "corr": corr, "trend": trend}


# ------------------------------------------------------------------ 5. Score
QUAD_SCORE = {"Improving": 1.0, "Leading": 0.75, "Weakening": -0.5, "Lagging": -0.75}


def score(ratio, mom, quad, stats, w=(0.4, 0.3, 0.2, 0.1)):
    """S = w1·z_cs(RS-Ratio) + w2·z_cs(RS-Mom) + w3·z_cs(Mom 12-1) + w4·QuadrantScore
       z_cs = z-score ข้ามหมวด ณ วันเดียวกัน (cross-sectional) เพื่อให้หน่วยเทียบกันได้
       QuadrantScore ให้ Improving สูงสุด ตามผลศึกษาว่าการเข้า Improving ให้ผล 21 วันถัดไปดีที่สุด"""
    cs = lambda x: x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0)
    q = quad.replace(QUAD_SCORE).astype(float)
    s = w[0] * cs(ratio) + w[1] * cs(mom) + w[2] * cs(stats["mom121"]) + w[3] * q
    return s.where(stats["trend"].notna())


# ------------------------------------------------------------------ 6–7. Select + Backtest
def backtest(idx: pd.DataFrame, bench: pd.Series, sc: pd.DataFrame, top=3, rebalance=4,
             cost_bps=15.0, trend=None, periods_per_year=52):
    """ถือ top-k หมวดคะแนนสูงสุด เท่า ๆ กัน, rebalance ทุก `rebalance` งวด
       ผลตอบแทนพอร์ต   R_p,t+1 = Σ w_i,t · r_i,t+1 − cost · turnover_t
       turnover_t     = ½ Σ |w_i,t − w_i,t−1|
       ถ้าใส่ trend   → หมวดที่อยู่ใต้เส้น 40 สัปดาห์จะถูกตัดออก (ส่วนที่เหลือถือเงินสด)"""
    r = idx.pct_change(fill_method=None).fillna(0)
    rb = bench.pct_change(fill_method=None).fillna(0)
    valid = sc.dropna(how="all").index
    start = valid[0] if len(valid) else idx.index[-1]
    dates = idx.index[idx.index >= start]
    w = pd.DataFrame(0.0, index=dates, columns=idx.columns)
    cur = pd.Series(0.0, index=idx.columns)
    for k, d in enumerate(dates):
        if k % rebalance == 0:
            s = sc.loc[d].dropna()
            if trend is not None:
                s = s[trend.loc[d, s.index] == 1]
            pick = s.nlargest(top).index
            cur = pd.Series(0.0, index=idx.columns)
            if len(pick):
                cur[pick] = 1.0 / top  # ช่องที่เลือกไม่ได้ = เงินสด
        w.loc[d] = cur
    turnover = w.diff().abs().sum(axis=1).fillna(w.iloc[0].abs().sum()) / 2
    gross = (w.shift(1) * r.loc[dates]).sum(axis=1)
    net = gross - turnover.shift(1).fillna(0) * cost_bps / 1e4
    ew = r.loc[dates].mean(axis=1)  # ถือทุกหมวดเท่ากัน — ใช้แยกผลของ "การเลือก" ออกจากผลของ "การถ่วงเท่ากัน"
    res = pd.DataFrame({"strategy": net, "benchmark": rb.loc[dates], "equal_weight_all": ew})
    return res, w, turnover


def metrics(res: pd.DataFrame, turnover: pd.Series, ppy=52) -> pd.DataFrame:
    """CAGR = (Π(1+r))^(ppy/N) − 1 ; Vol = σ·√ppy ; Sharpe = mean/σ·√ppy (rf=0)
       MaxDD = min(NAV/max(NAV) − 1) ; IR = mean(r_p − r_B)/σ(r_p − r_B)·√ppy"""
    out = {}
    for c in res:
        x = res[c].iloc[1:]
        nav = (1 + x).cumprod()
        out[c] = {
            "CAGR": nav.iloc[-1] ** (ppy / len(x)) - 1,
            "Vol": x.std() * np.sqrt(ppy),
            "Sharpe": x.mean() / x.std() * np.sqrt(ppy) if x.std() else np.nan,
            "MaxDD": (nav / nav.cummax() - 1).min(),
            "HitRate_vs_B": (x > res["benchmark"].iloc[1:]).mean(),
        }
    act = res["strategy"] - res["benchmark"]
    out["strategy"]["IR_vs_B"] = act.mean() / act.std() * np.sqrt(ppy)
    out["strategy"]["Turnover/yr"] = turnover.sum() / (len(res) / ppy)
    return pd.DataFrame(out).T


def snapshot(ratio, mom, quad, heading, stats, sc) -> pd.DataFrame:
    """ตารางสถานะล่าสุดของทุกหมวด เรียงตามคะแนน"""
    t = ratio.index[-1]
    df = pd.DataFrame({
        "quadrant": quad.loc[t], "rs_ratio": ratio.loc[t], "rs_mom": mom.loc[t], "heading": heading.loc[t],
        "excess_1y": stats["excess"].loc[t], "mom_12_1": stats["mom121"].loc[t],
        "beta_1y": stats["beta"].loc[t], "corr_1y": stats["corr"].loc[t], "above_40w": stats["trend"].loc[t],
        "score": sc.loc[t]})
    return df.sort_values("score", ascending=False).round(3)


def top_stocks(prices: pd.DataFrame, bench: pd.Series, members: list[str], n=14, k=2) -> pd.DataFrame:
    """ขั้นที่สองของ top-down: ในหมวดที่เลือก จัดอันดับหุ้นด้วย RRG เดียวกัน (เทียบ benchmark)"""
    syms = [s for s in members if s in prices]
    _, ratio, mom, quad, _ = rrg(prices[syms], bench, n)
    t = ratio.index[-1]
    df = pd.DataFrame({"quadrant": quad.loc[t], "rs_ratio": ratio.loc[t], "rs_mom": mom.loc[t]})
    df["score"] = df.rs_ratio.rank() + df.rs_mom.rank()
    return df.sort_values("score", ascending=False).head(k).round(2)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="set", choices=list(PRESETS))
    ap.add_argument("--window", type=int, default=14)
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--rebalance", type=int, default=4, help="จำนวนสัปดาห์ต่อรอบ rebalance")
    ap.add_argument("--cost", type=float, default=15.0, help="ค่าธรรมเนียม+slippage ต่อข้าง (bps)")
    ap.add_argument("--trend-filter", action="store_true")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    P = PRESETS[a.preset]
    members = {sec: [s + P["suffix"] for s in syms] for sec, syms in P["sectors"].items()}
    allsyms = sorted({s for v in members.values() for s in v})
    prices = load_prices(allsyms, P["bench"])
    bench = prices[P["bench"]]

    idx = sector_index(prices, members)
    rs, ratio, mom, quad, heading = rrg(idx, bench, a.window)
    stats = relative_stats(idx, bench)
    sc = score(ratio, mom, quad, stats)
    res, w, to = backtest(idx, bench, sc, a.top, a.rebalance, a.cost,
                          trend=stats["trend"] if a.trend_filter else None)

    os.makedirs(a.out, exist_ok=True)
    snap = snapshot(ratio, mom, quad, heading, stats, sc)
    m = metrics(res, to)
    snap.to_csv(f"{a.out}/snapshot.csv")
    m.to_csv(f"{a.out}/metrics.csv")
    (1 + res).cumprod().to_csv(f"{a.out}/nav.csv")
    w[w.ne(w.shift())].dropna(how="all").to_csv(f"{a.out}/weights.csv")
    pd.concat([idx, bench.rename("BENCH")], axis=1).to_csv(f"{a.out}/sector_index.csv")

    pd.set_option("display.width", 160)
    print(f"\n== สถานะล่าสุด {ratio.index[-1].date()} (vs {P['bench']}, window {a.window}) ==")
    print(snap)
    print(f"\n== Backtest {res.index[1].date()} → {res.index[-1].date()} · top {a.top} · rebalance {a.rebalance}w · cost {a.cost}bps ==")
    print(m.round(3))
    print("\n== หุ้นเด่นในหมวดที่ได้คะแนนสูงสุด ==")
    for sec in snap.index[: a.top]:
        print(sec, top_stocks(prices, bench, members[sec], a.window).to_dict("index"))


if __name__ == "__main__":
    main()
