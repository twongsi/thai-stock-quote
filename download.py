"""Download weekly quotes for each ticker in tickers.csv from Yahoo Finance.

Only new weeks are fetched when data/<TICKER>.csv already exists. The SET
index (^SET.BI) is saved to data/index/SET.csv as a benchmark.

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
INDEX_SYMBOLS = {'SET': '^SET.BI'}


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
    raw = yf.Ticker(symbol).history(start=start, interval='1wk', auto_adjust=False, actions=False)
    if raw.empty:
        return None
    raw = raw.reset_index()
    raw['Date'] = week_start(raw['Date'])
    return raw[['Date'] + COLUMNS]


def merge(existing, new):
    """New rows win where weeks overlap (the last week is usually partial)."""
    if existing is None:
        return new
    df = pd.concat([existing, new]).drop_duplicates('Date', keep='last')
    return df.sort_values('Date').reset_index(drop=True)


def update(symbol, path, full=False):
    existing = None if full else load_existing(path)
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

    failed = []
    jobs = [(t + '.BK', f'data/{t}.csv') for t in tickers]
    jobs += [(sym, f'data/index/{name}.csv') for name, sym in INDEX_SYMBOLS.items()]
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
