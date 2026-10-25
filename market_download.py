"""Download weekly quotes for every stock on SET and mai from Yahoo Finance.

The stock list comes from set.or.th (see market_coverage.py) and is saved to
data/market/symbols.csv with each symbol's market, sector and kind (company or
property fund/REIT). Prices go to data/market/prices/<TICKER>.csv in the same
format as data/<TICKER>.csv. Stocks are fetched in batches; after the first run
only the last few weeks are fetched.

    python market_download.py
    python market_download.py --full        # refetch all history
"""
import argparse
import os
import sys

import pandas as pd
import yfinance as yf

import market_coverage as mc
import download
from download import COLUMNS, load_existing, merge, week_start

OUT_DIR = 'data/market'
# Ten years is plenty for the screener; the SET100 files in data/ go back to 2010
START_DATE = '2016-01-01'
BATCH = 100


def start_for(existing, full=False):
    if full or existing is None or len(existing) < 52:
        return START_DATE
    # Re-fetch the last few weeks so a partial week and late corrections are refreshed
    return (existing['Date'].max() - pd.Timedelta(weeks=2)).strftime('%Y-%m-%d')


def frames_by_symbol(data, yahoo_symbols):
    """Split a yf.download result into one weekly DataFrame per Yahoo symbol."""
    if data.empty:
        return {}
    if not isinstance(data.columns, pd.MultiIndex):
        data = pd.concat({yahoo_symbols[0]: data}, axis=1)   # single-ticker batch
    out = {}
    for sym in yahoo_symbols:
        if sym not in data.columns.get_level_values(0):
            continue
        df = data[sym].dropna(subset=['Close'])
        if df.empty:
            continue
        df = df.reset_index().rename(columns={df.index.name or 'index': 'Date'})
        df['Date'] = week_start(df['Date'])
        out[sym] = df.drop_duplicates('Date', keep='last')[['Date'] + COLUMNS]
    return out


def fetch_batch(symbols, start):
    yahoo = [s + '.BK' for s in symbols]
    data = yf.download(yahoo, start=start, interval='1wk', group_by='ticker', auto_adjust=False,
                       actions=False, progress=False, threads=True)
    return {s[:-3]: df for s, df in frames_by_symbol(data, yahoo).items()}


def retry_short(symbols, frames, min_weeks=52):
    """Refetch, one at a time, symbols the batch missed or returned under a year for.

    Yahoo's weekly batch sometimes returns only the latest bars of a stock with a
    long history (seen for QUICK and MJLF); download.fetch rebuilds the weeks from
    daily bars in that case. New listings stay short, which is correct.
    """
    out = {}
    for s in symbols:
        if s in frames and len(frames[s]) >= min_weeks:
            continue
        try:
            df = download.fetch(s + '.BK', START_DATE)
        except Exception as e:
            print(f'{s}: retry failed ({e})')
            continue
        if df is not None and len(df) > len(frames.get(s, [])):
            out[s] = df
    return out


def update_all(symbols, price_dir, full=False):
    """Fetch and save every symbol; return the symbols Yahoo had no data for."""
    os.makedirs(price_dir, exist_ok=True)
    existing = {s: (None if full else load_existing(os.path.join(price_dir, f'{s}.csv'))) for s in symbols}
    # Group by start date so one new listing doesn't force ten years for a whole batch
    by_start = {}
    for s in symbols:
        by_start.setdefault(start_for(existing[s], full) == START_DATE, []).append(s)
    failed = []
    for needs_full, group in sorted(by_start.items()):
        start = START_DATE if needs_full else min(start_for(existing[s]) for s in group)
        for i in range(0, len(group), BATCH):
            chunk = group[i:i + BATCH]
            frames = fetch_batch(chunk, start)
            if needs_full:
                frames.update(retry_short(chunk, frames))
            for s in chunk:
                if s not in frames:
                    failed.append(s)
                    continue
                old = None if needs_full else existing[s]
                merge(old, frames[s]).to_csv(os.path.join(price_dir, f'{s}.csv'),
                                             index=False, date_format='%Y-%m-%d')
            print(f'{"full" if needs_full else "update"} from {start}: '
                  f'{min(i + BATCH, len(group))}/{len(group)}')
    return failed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=OUT_DIR)
    ap.add_argument('--full', action='store_true', help='ignore existing files and refetch from ' + START_DATE)
    args = ap.parse_args()

    symbols_path = os.path.join(args.out, 'symbols.csv')
    try:
        universe = mc.common_stocks(mc.list_rows(mc.stock_list(mc.market_session())), ['set', 'mai'])
    except Exception as e:
        print(f'stock list failed: {e}')
        universe = pd.DataFrame()
    if universe.empty:
        if not os.path.exists(symbols_path):
            sys.exit('no stock list from set.or.th and no saved symbols.csv')
        print(f'using the saved {symbols_path}')
        universe = pd.read_csv(symbols_path)
    else:
        os.makedirs(args.out, exist_ok=True)
        universe.to_csv(symbols_path, index=False)
    print(f'{len(universe)} stocks: '
          + ', '.join(f'{m} {k}={n}' for (m, k), n in universe.groupby(['market', 'kind']).size().items()))

    failed = update_all(universe['symbol'].tolist(), os.path.join(args.out, 'prices'), args.full)
    print(f'saved {len(universe) - len(failed)} of {len(universe)}')
    if failed:
        print(f'no data for {len(failed)}: {", ".join(failed)}')
    if len(failed) > len(universe) // 2:
        sys.exit('most downloads failed; check network or Yahoo availability')


if __name__ == '__main__':
    main()
