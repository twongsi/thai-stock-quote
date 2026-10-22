"""Snapshot an analyst-consensus table (target price, ratings, EPS estimates).

Default source: https://9hoon.com/aset/view_analyst_consensus.php

The page layout was not verified when this was written, so no column names
are hard-coded: the script picks the HTML table whose cells contain the most
SET100 tickers from tickers.csv and saves it as-is, with numeric clean-up.
Run recon.py on the page first and use --table / --symbol-col if the
automatic pick is wrong.

    python consensus.py
    python consensus.py --source recon/aset_view_analyst_consensus.php.html
    python consensus.py --all-symbols        # keep non-SET100 rows too
"""
import argparse
import csv
import datetime as dt
import os
from io import StringIO

import pandas as pd
import requests

DEFAULT_URL = 'https://9hoon.com/aset/view_analyst_consensus.php'
USER_AGENT = 'Mozilla/5.0 (thai-stock-quote research script)'


def load_tickers(path='tickers.csv'):
    with open(path, newline='') as f:
        return set(list(csv.reader(f))[0])


def read_source(source):
    if source.startswith('http'):
        resp = requests.get(source, headers={'User-Agent': USER_AGENT}, timeout=30)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        return resp.text
    with open(source, encoding='utf-8', errors='replace') as f:
        return f.read()


def ticker_hits(df, tickers):
    """Return (best column, number of SET100 tickers found in it)."""
    best = (None, 0)
    for col in df.columns:
        values = df[col].astype(str).str.strip().str.upper()
        hits = values.isin(tickers).sum()
        if hits > best[1]:
            best = (col, hits)
    return best


def pick_table(tables, tickers, table_index=None, symbol_col=None):
    if table_index is not None:
        df = tables[table_index]
        return df, symbol_col or ticker_hits(df, tickers)[0]
    scored = [(ticker_hits(t, tickers), i) for i, t in enumerate(tables)]
    (col, hits), i = max(scored, key=lambda s: s[0][1])
    if hits == 0:
        raise SystemExit('No table contains SET100 tickers; run recon.py and pass --table/--symbol-col.')
    print(f'using table {i}: {hits} SET100 tickers in column {col!r}')
    return tables[i], symbol_col or col


def clean(df, symbol_col):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [' '.join(str(p) for p in c if not str(p).startswith('Unnamed')).strip()
                      for c in df.columns]
        symbol_col = ' '.join(str(p) for p in symbol_col if not str(p).startswith('Unnamed')).strip() \
            if isinstance(symbol_col, tuple) else symbol_col
    df = df.rename(columns={symbol_col: 'Symbol'})
    df['Symbol'] = df['Symbol'].astype(str).str.strip().str.upper()
    for col in df.columns.drop('Symbol'):
        text = df[col].astype(str).str.replace(',', '').str.replace('%', '').str.strip()
        text = text.where(~text.isin(['-', '', 'N/A', 'nan', 'NaN']))
        as_num = pd.to_numeric(text, errors='coerce')
        # Only convert columns that are mostly numbers; leave ratings/text alone
        if as_num.notna().sum() >= 0.8 * text.notna().sum():
            df[col] = as_num
    return df


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--source', default=DEFAULT_URL, help='URL or saved .html file')
    ap.add_argument('--table', type=int, help='index of the table to use (see recon.py)')
    ap.add_argument('--symbol-col', help='name of the ticker column')
    ap.add_argument('--all-symbols', action='store_true', help='keep rows outside SET100')
    ap.add_argument('--out-dir', default='data/consensus')
    args = ap.parse_args()

    tickers = load_tickers()
    tables = pd.read_html(StringIO(read_source(args.source)))
    df, symbol_col = pick_table(tables, tickers, args.table, args.symbol_col)
    df = clean(df, symbol_col)
    if not args.all_symbols:
        df = df[df['Symbol'].isin(tickers)]
    df.insert(0, 'SnapshotDate', dt.date.today().isoformat())

    os.makedirs(args.out_dir, exist_ok=True)
    path = os.path.join(args.out_dir, f'{dt.date.today().isoformat()}.csv')
    df.to_csv(path, index=False)
    print(f'{len(df)} rows -> {path}')
    missing = sorted(tickers - set(df['Symbol']))
    if missing:
        print(f'{len(missing)} SET100 tickers not in the table: {", ".join(missing)}')


if __name__ == '__main__':
    main()
