"""Test which SET and mai stocks the data sources cover.

Gets every common stock listed on SET and mai from set.or.th's stock list (the
index composition endpoint returns 404 for 'set' and 'mai'), then checks each
symbol against:
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
from get_tickers import HEADERS

STOCK_LIST_URL = 'https://www.set.or.th/api/set/stock/list'
STOCK_LIST_PAGE = 'https://www.set.or.th/en/market/get-quote/stock/'
BATCH = 100


def market_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def stock_list(session):
    session.get(STOCK_LIST_PAGE, timeout=30)   # the API expects a normal page visit first
    resp = session.get(STOCK_LIST_URL, headers={'Referer': STOCK_LIST_PAGE}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def list_rows(payload):
    rows = payload.get('securitySymbols', []) if isinstance(payload, dict) else payload
    return pd.DataFrame([{
        'symbol': str(r['symbol']).strip().upper(),
        'market': 'SET' if str(r.get('market', '')).lower() == 'set' else str(r.get('market', '')),
        'security_type': r.get('securityType'),
        'industry': r.get('industry'),
        'sector': r.get('sector'),
    } for r in rows if isinstance(r, dict) and r.get('symbol')])


def common_stocks(rows, markets):
    """Common stocks of the given markets, one row per symbol."""
    if rows.empty:
        return rows
    # 'S' = common stock; warrants, DRs, ETFs and funds use other codes
    keep = rows['market'].str.lower().isin(markets) & \
        (rows['security_type'].isna() | (rows['security_type'] == 'S'))
    return rows[keep].drop_duplicates('symbol').sort_values('symbol').reset_index(drop=True)


def stock_list_symbols(payload, market):
    rows = common_stocks(list_rows(payload), [market])
    return rows['symbol'].tolist() if not rows.empty else []


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

    rows = list_rows(stock_list(market_session()))
    for market in args.markets:
        mine = rows[rows['market'].str.lower() == market]
        print(f'{market}: {len(mine)} securities by type: '
              + ', '.join(f'{k}={v}' for k, v in mine['security_type'].fillna('none').value_counts().items()))
    universe = common_stocks(rows, args.markets)
    for market, g in universe.groupby('market'):
        print(f'{market} type S by sector: '
              + ', '.join(f'{k}={v}' for k, v in g['sector'].fillna('none').value_counts().items()))
        funds = g[g['sector'].fillna('').str.upper().str.contains('REIT|PF|FUND|INFRA')]
        if len(funds):
            print(f'  funds/REITs ({len(funds)}): {", ".join(funds["symbol"])}')
    print(f'{len(universe)} common stocks to check')
    if universe.empty:
        sys.exit('no common stocks found in the stock list')
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
