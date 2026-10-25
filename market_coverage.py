"""Test which SET and mai stocks the data sources cover.

Gets every constituent of the SET and mai indices from set.or.th (same JSON API
as get_tickers.py), then checks each symbol against:
  - Yahoo Finance: daily bars over the last month (yfinance, in batches)
  - 9hoon: whether the analyst-consensus table has a row for it

Writes <out>/symbols.csv and <out>/coverage.csv and prints a summary per market.

    python market_coverage.py
    python market_coverage.py --markets mai --out reports/market
"""
import argparse
import os
import sys
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

import consensus
from get_tickers import HEADERS, extract_symbols

COMPOSITION_URL = 'https://www.set.or.th/api/set/index/{index}/composition'
OVERVIEW_URL = 'https://www.set.or.th/en/market/index/{index}/overview'
STOCK_LIST_URL = 'https://www.set.or.th/api/set/stock/list'
# Rough constituent counts; fewer than this means the response was not the full list
MIN_SYMBOLS = {'set': 300, 'mai': 100}
BATCH = 100


def market_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def composition(session, index):
    referer = OVERVIEW_URL.format(index=index)
    session.get(referer, timeout=30)   # the API expects a normal page visit first
    resp = session.get(COMPOSITION_URL.format(index=index), params={'lang': 'en'},
                       headers={'Referer': referer}, timeout=30)
    resp.raise_for_status()
    return extract_symbols(resp.json())


def stock_list_symbols(payload, market):
    """Common stocks of one market from the /stock/list response."""
    rows = payload.get('securitySymbols', []) if isinstance(payload, dict) else payload
    out = []
    for row in rows:
        if not isinstance(row, dict) or not row.get('symbol'):
            continue
        if str(row.get('market', '')).lower() != market:
            continue
        # 'S' = common stock; warrants, DRs, ETFs and preferred shares use other codes
        if row.get('securityType') not in (None, 'S'):
            continue
        out.append(row['symbol'].strip().upper())
    return sorted(set(out))


def market_symbols(session, market):
    try:
        symbols = composition(session, market)
        if len(symbols) >= MIN_SYMBOLS[market]:
            return symbols, 'index composition'
        print(f'{market}: composition returned {len(symbols)} symbols, trying the stock list')
    except Exception as e:
        print(f'{market}: composition failed ({e}), trying the stock list')
    resp = session.get(STOCK_LIST_URL, timeout=30)
    resp.raise_for_status()
    return stock_list_symbols(resp.json(), market), 'stock list'


def yahoo_coverage(symbols, period='1mo'):
    rows = []
    for i in range(0, len(symbols), BATCH):
        chunk = symbols[i:i + BATCH]
        yahoo = [s + '.BK' for s in chunk]
        data = yf.download(yahoo, period=period, interval='1d', group_by='ticker',
                           auto_adjust=False, progress=False, threads=True)
        if not data.empty and not isinstance(data.columns, pd.MultiIndex):
            data = pd.concat({yahoo[0]: data}, axis=1)   # single-ticker batch
        have = set(data.columns.get_level_values(0)) if not data.empty else set()
        for sym, ysym in zip(chunk, yahoo):
            df = data[ysym].dropna(subset=['Close']) if ysym in have else pd.DataFrame()
            rows.append({
                'symbol': sym,
                'yahoo_days': len(df),
                'yahoo_last_date': df.index[-1].date() if len(df) else None,
                'yahoo_close': df['Close'].iloc[-1] if len(df) else None,
                'yahoo_avg_value_mb': (df['Close'] * df['Volume']).mean() / 1e6 if len(df) else None,
            })
        print(f'yahoo: {min(i + BATCH, len(symbols))}/{len(symbols)}')
    return pd.DataFrame(rows)


def hoon_coverage(symbols):
    tables = pd.read_html(StringIO(consensus.read_source(consensus.DEFAULT_URL)))
    df, col = consensus.pick_table(tables, set(symbols))
    df = consensus.clean(df, col).drop_duplicates('Symbol')
    keep = {'Symbol': 'symbol'}
    for c in df.columns:
        if 'cover' in c.lower():
            keep[c] = 'hoon_analysts'
        elif 'upside' in c.lower():
            keep[c] = 'hoon_upside'
    return df[list(keep)].rename(columns=keep).assign(in_9hoon=True)


def summarize(cov):
    lines = []
    for market, g in cov.groupby('market'):
        n = len(g)
        yahoo = (g['yahoo_days'] > 0).sum()
        hoon = g['in_9hoon'].sum()
        analysts = (g.get('hoon_analysts', pd.Series(dtype=float)) > 0).sum()
        lines.append(f'{market}: {n} stocks | Yahoo {yahoo} ({yahoo / n:.0%}) | '
                     f'9hoon {hoon} ({hoon / n:.0%}), with analysts {analysts}')
        missing = g.loc[g['yahoo_days'] == 0, 'symbol'].tolist()
        if missing:
            lines.append(f'  no Yahoo data ({len(missing)}): {", ".join(missing)}')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--markets', nargs='+', default=['set', 'mai'], choices=['set', 'mai'])
    ap.add_argument('--out', default='reports/market')
    args = ap.parse_args()

    session = market_session()
    frames = []
    for market in args.markets:
        symbols, source = market_symbols(session, market)
        print(f'{market}: {len(symbols)} symbols from {source}')
        frames.append(pd.DataFrame({'symbol': symbols, 'market': market.upper() if market == 'set' else market}))
    universe = pd.concat(frames, ignore_index=True).drop_duplicates('symbol')
    if universe.empty:
        sys.exit('no symbols found')
    os.makedirs(args.out, exist_ok=True)
    universe.to_csv(os.path.join(args.out, 'symbols.csv'), index=False)

    cov = universe.merge(yahoo_coverage(universe['symbol'].tolist()), on='symbol', how='left')
    try:
        cov = cov.merge(hoon_coverage(universe['symbol'].tolist()), on='symbol', how='left')
    except Exception as e:
        print(f'9hoon: {e}')
    if 'in_9hoon' not in cov:
        cov['in_9hoon'] = False
    cov['in_9hoon'] = cov['in_9hoon'].fillna(False).astype(bool)
    cov.to_csv(os.path.join(args.out, 'coverage.csv'), index=False)

    summary = summarize(cov)
    print('\n' + summary)
    with open(os.path.join(args.out, 'summary.txt'), 'w') as f:
        f.write(summary + '\n')


if __name__ == '__main__':
    main()
