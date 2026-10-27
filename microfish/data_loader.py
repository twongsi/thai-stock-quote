"""Stage 1 -- build a factual market snapshot from raw OHLCV data.

This is the equities analogue of MiroFish's "graph construction from seed
data": we distil the raw price history into a compact set of facts the agents
can reason over, so that no agent has to eyeball a giant CSV.
"""

from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass, field
from statistics import mean, pstdev

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


@dataclass
class MarketSnapshot:
    """A compact, agent-readable summary of a stock's recent behaviour."""

    ticker: str
    as_of: str
    last_close: float
    lookback_weeks: int
    change_pct: float          # total % change over the lookback window
    momentum_score: float      # normalised trend strength, roughly [-3, 3]
    annualised_vol_pct: float  # weekly-return volatility, annualised
    ma_short: float            # short moving average of close
    ma_long: float             # long moving average of close
    high_52w: float
    low_52w: float
    drawdown_pct: float        # % below the 52-week high
    recent_closes: list[float] = field(default_factory=list)
    notes: str = ""

    def to_facts(self) -> str:
        """Render the snapshot as a plain-text fact sheet for prompting."""
        trend = "up" if self.change_pct > 0 else "down" if self.change_pct < 0 else "flat"
        ma_state = "above" if self.ma_short >= self.ma_long else "below"
        lines = [
            f"Ticker: {self.ticker} (Thai SET)",
            f"As of: {self.as_of}  (weekly bars, {self.lookback_weeks}-week lookback)",
            f"Last close: {self.last_close:.2f}",
            f"Window change: {self.change_pct:+.1f}% (trend {trend})",
            f"Momentum score: {self.momentum_score:+.2f}  (positive = up-trend)",
            f"Short MA {self.ma_short:.2f} is {ma_state} long MA {self.ma_long:.2f}",
            f"Annualised volatility: {self.annualised_vol_pct:.0f}%",
            f"52w high/low: {self.high_52w:.2f} / {self.low_52w:.2f}",
            f"Drawdown from high: {self.drawdown_pct:.1f}%",
            f"Recent closes: {', '.join(f'{c:.2f}' for c in self.recent_closes[-10:])}",
        ]
        if self.notes:
            lines.append(f"Seed context: {self.notes}")
        return "\n".join(lines)


def _read_rows(path: str) -> list[dict]:
    with open(path, newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            close = row.get("Close") or row.get("Adj Close")
            try:
                c = float(close)
            except (TypeError, ValueError):
                continue
            if math.isnan(c):
                continue
            rows.append({"date": row.get("Date", ""), "close": c})
        return rows


def load_snapshot(
    ticker: str,
    *,
    data_dir: str | None = None,
    lookback_weeks: int = 52,
    notes: str = "",
) -> MarketSnapshot:
    """Load ``<ticker>.csv`` and distil it into a :class:`MarketSnapshot`."""
    data_dir = data_dir or DATA_DIR
    path = os.path.join(data_dir, f"{ticker}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No data file for ticker {ticker!r}: {path}")

    rows = _read_rows(path)
    if len(rows) < 5:
        raise ValueError(f"Not enough price history for {ticker!r} ({len(rows)} rows).")

    window = rows[-lookback_weeks:] if lookback_weeks else rows
    closes = [r["close"] for r in window]
    all_closes = [r["close"] for r in rows]

    last_close = closes[-1]
    first_close = closes[0]
    change_pct = (last_close / first_close - 1.0) * 100.0 if first_close else 0.0

    # Weekly log returns -> volatility (annualised, 52 weeks/year).
    rets = [
        math.log(closes[i] / closes[i - 1])
        for i in range(1, len(closes))
        if closes[i - 1] > 0
    ]
    weekly_vol = pstdev(rets) if len(rets) > 1 else 0.0
    ann_vol_pct = weekly_vol * math.sqrt(52) * 100.0

    ma_short = mean(closes[-8:]) if len(closes) >= 8 else mean(closes)
    ma_long = mean(closes[-26:]) if len(closes) >= 26 else mean(closes)

    # Momentum: window return scaled by its own volatility (a t-stat-ish score).
    total_ret = math.log(last_close / first_close) if first_close > 0 else 0.0
    denom = (weekly_vol * math.sqrt(len(rets))) if rets else 0.0
    momentum = total_ret / denom if denom > 0 else 0.0
    momentum = max(-3.0, min(3.0, momentum))

    high_52w = max(all_closes[-lookback_weeks:]) if lookback_weeks else max(all_closes)
    low_52w = min(all_closes[-lookback_weeks:]) if lookback_weeks else min(all_closes)
    drawdown_pct = (last_close / high_52w - 1.0) * 100.0 if high_52w else 0.0

    return MarketSnapshot(
        ticker=ticker,
        as_of=window[-1]["date"],
        last_close=last_close,
        lookback_weeks=len(window),
        change_pct=change_pct,
        momentum_score=momentum,
        annualised_vol_pct=ann_vol_pct,
        ma_short=ma_short,
        ma_long=ma_long,
        high_52w=high_52w,
        low_52w=low_52w,
        drawdown_pct=drawdown_pct,
        recent_closes=closes,
        notes=notes,
    )
