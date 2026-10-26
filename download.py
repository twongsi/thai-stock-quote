"""Download weekly quotes for each ticker in tickers.csv from Yahoo Finance.

Only new weeks are fetched when data/<TICKER>.csv already exists. The SET
index (^SET.BK) and the TDEX SET50 ETF are saved to data/index/ as benchmarks.
QQQ, SPY, the ABFTH Thai bond ETF and the USD/THB rate are saved to
data/assets/ for the strategy sandbox's historical backtest.

    python download.py              # update everything
    python download.py PTT AOT      # update selected tickers
    python download.py --full       # refetch all history
"""
import argparse
import csv
import os
import time

import pandas as pd
import yfinance as yf

START_DATE = '2010-01-01'
COLUMNS = ['High', 'Low', 'Open', 'Close', 'Volume', 'Adj Close']
# Yahoo has almost no history for ^SET.BK; TDEX (an ETF tracking the SET50)
# has prices back to 2007 and stands in as the long-run benchmark
INDEX_SYMBOLS = {'SET': '^SET.BK', 'TDEX': 'TDEX.BK'}
# Proxies for the other sleeves of docs/strategy-sandbox.html. Kept out of
# data/index/ so analytics.py doesn't treat USD series as SET benchmarks.
# USDTHB (THB per USD) converts QQQ and SPY returns into baht.
ASSET_SYMBOLS = {'QQQ': 'QQQ', 'SPY': 'SPY', 'ABFTH': 'ABFTH.BK', 'USDTHB': 'THB=X'}


def week_start(dates):
    """Map each date to the Monday of its trading week.

    Older files (pandas_datareader) stamp weeks on Sunday, which is Monday in
    Bangkok; yfinance stamps them on Monday. Normalising lets the two merge.
    """
    dates = pd.to_datetime(dates).dt.tz_localize(None).dt.normalize()
    sunday = dates.dt.weekday == 6
    dates = dates.where(~sunday, dates + pd.Timedelta(days=1))
    return dates - pd.to_timedelta(dates.dt.weekday, unit='D')


def load_existing(path):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df['Date'] = week_start(df['Date'])
    return df


def fetch(symbol, start):
    ticker = yf.Ticker(symbol)
    raw = ticker.history(start=start, interval='1wk', auto_adjust=False, actions=False)
    expected = (pd.Timestamp.now() - pd.Timestamp(start)).days // 7
    if len(raw) < expected // 2:
        # Yahoo sometimes returns only the latest weekly bar (seen for ^SET.BK);
        # its daily history is complete, so build the weeks from that
        daily = ticker.history(start=start, interval='1d', auto_adjust=False, actions=False)
        if len(daily) > len(raw):
            raw = to_weekly(daily)
    if raw.empty:
        return None
    raw = raw.reset_index()
    raw['Date'] = week_start(raw['Date'])
    return raw.drop_duplicates('Date', keep='last')[['Date'] + COLUMNS]


def to_weekly(daily):
    daily = daily.copy()
    daily.index = daily.index.tz_localize(None) if daily.index.tz is not None else daily.index
    weekly = daily.resample('W-MON', label='left', closed='left').agg({
        'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last',
        'Adj Close': 'last', 'Volume': 'sum'}).dropna(subset=['Close'])
    weekly.index.name = 'Date'
    return weekly


def merge(existing, new):
    """New rows win where weeks overlap (the last week is usually partial)."""
    if existing is None:
        return new
    df = pd.concat([existing, new]).drop_duplicates('Date', keep='last')
    return df.sort_values('Date').reset_index(drop=True)


def update(symbol, path, full=False):
    existing = None if full else load_existing(path)
    if existing is not None and len(existing) < 52:
        existing = None   # too short to extend; fetch the full history
    # Re-fetch the last few weeks so a partial week and late corrections are refreshed
    start = START_DATE if existing is None or existing.empty else \
        (existing['Date'].max() - pd.Timedelta(weeks=2)).strftime('%Y-%m-%d')
    new = fetch(symbol, start)
    if new is None:
        return 0
    df = merge(existing, new)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, date_format='%Y-%m-%d')
    return len(new)


def move_former_members(tickers, data_dir='data'):
    """Keep data/ to current members; older files go to data/former/."""
    current = set(tickers)
    for name in sorted(os.listdir(data_dir)):
        ticker, ext = os.path.splitext(name)
        if ext == '.csv' and ticker not in current:
            os.makedirs(os.path.join(data_dir, 'former'), exist_ok=True)
            os.replace(os.path.join(data_dir, name), os.path.join(data_dir, 'former', name))
            print(f'{ticker} left SET100 -> data/former/{name}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('tickers', nargs='*', help='default: all in tickers.csv')
    ap.add_argument('--full', action='store_true', help='ignore existing files and refetch from 2010')
    args = ap.parse_args()

    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
    else:
        with open('tickers.csv', newline='') as f:
            tickers = [t.strip() for t in list(csv.reader(f))[0] if t.strip()]
        move_former_members(tickers)

    failed = []
    jobs = [(t + '.BK', f'data/{t}.csv') for t in tickers]
    jobs += [(sym, f'data/index/{name}.csv') for name, sym in INDEX_SYMBOLS.items()]
    jobs += [(sym, f'data/assets/{name}.csv') for name, sym in ASSET_SYMBOLS.items()]
    for symbol, path in jobs:
        try:
            n = update(symbol, path, args.full)
            print(f'{symbol:12} {n:4d} weeks fetched')
            if n == 0:
                failed.append(symbol)
        except Exception as e:
            print(f'{symbol:12} error: {e}')
            failed.append(symbol)
        time.sleep(0.5)

    if failed:
        print(f'no data for {len(failed)}: {", ".join(failed)}')
    if len(failed) > len(jobs) // 2:
        raise SystemExit('most downloads failed; check network or Yahoo availability')


if __name__ == '__main__':
    main()
