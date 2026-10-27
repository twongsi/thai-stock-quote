"""คำนวณผลตอบแทนและค่าความเสี่ยงจากอนุกรม NAV รายวัน

อินพุตคือ list ของ (วันที่ 'YYYY-MM-DD', NAV ต่อหน่วย) เรียงจากเก่าไปใหม่
ทุกฟังก์ชันใช้ standard library ล้วน ๆ
"""

from __future__ import annotations

import math
from bisect import bisect_right
from datetime import date, timedelta

TRADING_DAYS = 252
DEFAULT_RISK_FREE = 0.02  # อัตราผลตอบแทนปราศจากความเสี่ยงต่อปี (ปรับได้ผ่าน .env)

# ช่วงเวลามาตรฐานที่ใช้วัดผลตอบแทน (ชื่อ, จำนวนวันตามปฏิทิน)
PERIODS: list[tuple[str, int | None]] = [
    ("1M", 30),
    ("3M", 91),
    ("6M", 182),
    ("YTD", None),   # ต้นปีถึงปัจจุบัน
    ("1Y", 365),
    ("3Y", 365 * 3),
    ("5Y", 365 * 5),
    ("MAX", -1),     # ตั้งแต่วันแรกที่มีข้อมูล
]


def parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


def clean_series(rows: list[tuple[str, float]]) -> list[tuple[date, float]]:
    """ทิ้งค่าที่ใช้ไม่ได้ (NAV <= 0 หรือ null) แล้วเรียงตามวันที่ + ตัดวันซ้ำ"""
    out: dict[date, float] = {}
    for raw_date, raw_nav in rows:
        if raw_date is None or raw_nav is None:
            continue
        try:
            d = parse_date(str(raw_date))
            v = float(raw_nav)
        except (ValueError, TypeError):
            continue
        if v <= 0:
            continue
        out[d] = v
    return sorted(out.items())


def value_on_or_before(series: list[tuple[date, float]], target: date) -> tuple[date, float] | None:
    """หาค่า NAV ของวันทำการล่าสุดที่ <= target (กองทุนไม่มี NAV ทุกวันปฏิทิน)"""
    if not series:
        return None
    dates = [d for d, _ in series]
    idx = bisect_right(dates, target) - 1
    if idx < 0:
        return None
    return series[idx]


def slice_since(series: list[tuple[date, float]], start: date) -> list[tuple[date, float]]:
    dates = [d for d, _ in series]
    idx = bisect_right(dates, start) - 1
    idx = max(idx, 0)
    return series[idx:]


def simple_returns(series: list[tuple[date, float]]) -> list[float]:
    out = []
    for (_, prev), (_, cur) in zip(series, series[1:]):
        if prev > 0:
            out.append(cur / prev - 1.0)
    return out


def stdev(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return math.sqrt(var)


def annualize(total_return: float, days: int) -> float | None:
    """แปลงผลตอบแทนสะสมเป็นต่อปี (ใช้เมื่อช่วงเวลามากกว่า 1 ปี)"""
    if days <= 0 or total_return <= -1:
        return None
    return (1.0 + total_return) ** (365.0 / days) - 1.0


def max_drawdown(series: list[tuple[date, float]]) -> dict:
    """ขาดทุนสูงสุดจากจุดสูงสุดถึงจุดต่ำสุด (peak-to-trough)"""
    if len(series) < 2:
        return {"value": None, "peak_date": None, "trough_date": None, "recovery_days": None}
    peak_value = series[0][1]
    peak_date = series[0][0]
    worst = 0.0
    worst_peak = peak_date
    worst_trough = peak_date
    for d, v in series:
        if v > peak_value:
            peak_value, peak_date = v, d
        dd = v / peak_value - 1.0
        if dd < worst:
            worst, worst_peak, worst_trough = dd, peak_date, d

    # นับวันที่ใช้ฟื้นกลับไปเท่าจุดสูงสุดเดิม (ถ้ายังไม่ฟื้น = None)
    recovery_days = None
    peak_level = dict(series).get(worst_peak)
    if peak_level:
        for d, v in series:
            if d > worst_trough and v >= peak_level:
                recovery_days = (d - worst_trough).days
                break
    return {
        "value": worst,
        "peak_date": worst_peak.isoformat(),
        "trough_date": worst_trough.isoformat(),
        "recovery_days": recovery_days,
    }


def period_return(series: list[tuple[date, float]], label: str, days: int | None) -> dict:
    """ผลตอบแทนของช่วงเวลาหนึ่ง พร้อมบอกว่าข้อมูลครบช่วงหรือไม่"""
    if len(series) < 2:
        return {"period": label, "return": None, "annualized": None, "available": False}
    end_date, end_value = series[-1]

    if days == -1:
        start_date, start_value = series[0]
    else:
        if days is None:  # YTD
            target = date(end_date.year, 1, 1) - timedelta(days=1)
        else:
            target = end_date - timedelta(days=days)
        found = value_on_or_before(series, target)
        if not found:
            return {"period": label, "return": None, "annualized": None, "available": False}
        start_date, start_value = found
        # ถ้าข้อมูลเริ่มหลังวันที่ต้องการมากกว่า 10 วัน ถือว่าข้อมูลไม่ครบช่วง
        if days is not None and (start_date - target).days > 10:
            return {"period": label, "return": None, "annualized": None, "available": False}

    if start_value <= 0 or start_date == end_date:
        return {"period": label, "return": None, "annualized": None, "available": False}

    span = (end_date - start_date).days
    total = end_value / start_value - 1.0
    return {
        "period": label,
        "return": total,
        "annualized": annualize(total, span) if span > 400 else None,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "days": span,
        "available": True,
    }


def risk_metrics(series: list[tuple[date, float]], risk_free: float = DEFAULT_RISK_FREE) -> dict:
    """ความผันผวน, Sharpe, Sortino, Calmar, max drawdown จาก NAV จริง"""
    if len(series) < 20:
        return {"available": False}
    rets = simple_returns(series)
    if not rets:
        return {"available": False}

    span_days = (series[-1][0] - series[0][0]).days or 1
    obs_per_year = len(rets) * 365.0 / span_days
    obs_per_year = min(max(obs_per_year, 12.0), 366.0)

    vol = stdev(rets) * math.sqrt(obs_per_year)
    total = series[-1][1] / series[0][1] - 1.0
    ann_return = annualize(total, span_days)

    downside = [r for r in rets if r < 0]
    downside_dev = (math.sqrt(sum(r * r for r in downside) / len(rets)) * math.sqrt(obs_per_year)) if downside else 0.0

    dd = max_drawdown(series)
    sharpe = (ann_return - risk_free) / vol if (ann_return is not None and vol > 0) else None
    sortino = (ann_return - risk_free) / downside_dev if (ann_return is not None and downside_dev > 0) else None
    calmar = (ann_return / abs(dd["value"])) if (ann_return is not None and dd["value"]) else None

    # drawdown ณ ปัจจุบัน (ห่างจากจุดสูงสุดตลอดกาลเท่าไร)
    peak = max(v for _, v in series)
    current_dd = series[-1][1] / peak - 1.0 if peak > 0 else None

    positive = sum(1 for r in rets if r > 0)
    return {
        "available": True,
        "observations": len(rets) + 1,
        "start_date": series[0][0].isoformat(),
        "end_date": series[-1][0].isoformat(),
        "annualized_return": ann_return,
        "volatility": vol,
        "downside_deviation": downside_dev,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": dd["value"],
        "max_drawdown_peak": dd["peak_date"],
        "max_drawdown_trough": dd["trough_date"],
        "max_drawdown_recovery_days": dd["recovery_days"],
        "current_drawdown": current_dd,
        "best_day": max(rets),
        "worst_day": min(rets),
        "positive_day_ratio": positive / len(rets),
        "risk_free_rate": risk_free,
    }


def summarize(rows: list[tuple[str, float]], risk_free: float = DEFAULT_RISK_FREE) -> dict:
    """สรุปผลตอบแทนทุกช่วง + ค่าความเสี่ยง (ทั้งตลอดช่วงข้อมูล และ 1 ปีล่าสุด)"""
    series = clean_series(rows)
    if len(series) < 2:
        return {"available": False, "periods": [], "risk": {"available": False}}

    end_date = series[-1][0]
    one_year = slice_since(series, end_date - timedelta(days=365))
    three_year = slice_since(series, end_date - timedelta(days=365 * 3))

    latest_change = None
    if len(series) >= 2 and series[-2][1] > 0:
        latest_change = series[-1][1] / series[-2][1] - 1.0

    return {
        "available": True,
        "latest_nav": series[-1][1],
        "latest_date": end_date.isoformat(),
        "previous_nav": series[-2][1],
        "previous_date": series[-2][0].isoformat(),
        "daily_change": latest_change,
        "first_date": series[0][0].isoformat(),
        "periods": [period_return(series, label, days) for label, days in PERIODS],
        "risk": risk_metrics(series, risk_free),
        "risk_1y": risk_metrics(one_year, risk_free),
        "risk_3y": risk_metrics(three_year, risk_free),
    }


def indexed_series(rows: list[tuple[str, float]], start: date | None = None, base: float = 100.0) -> list[dict]:
    """ปรับฐาน NAV ให้เริ่มที่ 100 เพื่อเทียบหลายกองทุนบนกราฟเดียวกัน"""
    series = clean_series(rows)
    if start:
        series = slice_since(series, start)
    if not series:
        return []
    first = series[0][1]
    if first <= 0:
        return []
    return [{"d": d.isoformat(), "v": round(v / first * base, 4), "nav": v} for d, v in series]
