"""Filter SET100 stocks by technical indicators and 9hoon analyst consensus.

Reads the weekly quotes in data/ (SET100, download.py) or, with --universe all,
data/market/ (every SET and mai stock, market_download.py). With --consensus it
adds the newest 9hoon snapshot (consensus.py). analytics.py ranks stocks by a
fixed factor score; this script is for ad-hoc filters.

    python screener.py
    python screener.py --min-rsi 50 --above-sma 40 --golden-cross --near-high 5
    python screener.py --consensus --min-upside 15 --min-analysts 5 --rating Buy --sort upside
    python screener.py --consensus --max-pe 15 --min-div 4 --sort div_yield --csv value.csv
    python screener.py --universe all --market mai --kind company --min-value 5 --above-sma 40
    python screener.py --universe all --consensus --min-upside 20 --sector BANK --sector FIN
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd

from analytics import clean_prices
from consensus_history import pick_columns

DATA_DIR = 'data'
CONSENSUS_DIR = 'data/consensus'
MARKET_DIR = 'data/market'
UNIVERSES = {
    # universe: (price folder, consensus folder, symbols file)
    'set100': (DATA_DIR, CONSENSUS_DIR, None),
    'all': (os.path.join(MARKET_DIR, 'prices'), os.path.join(MARKET_DIR, 'consensus'),
            os.path.join(MARKET_DIR, 'symbols.csv')),
}

COLUMNS = ['ticker', 'date', 'close', 'ret_1w', 'ret_4w', 'ret_13w', 'ret_52w',
           'from_high_52w', 'from_low_52w', 'sma_10w', 'sma_40w', 'rsi_14',
           'volatility', 'avg_volume', 'avg_value_mb']
CONSENSUS_COLUMNS = ['median_target', 'upside', 'analysts', 'rating', 'pe', 'pbv', 'div_yield']
# 9hoon's trailing ratios; the forward P/E columns (P/E 2569F) are left out
FUNDAMENTALS = {'pe': 'p/e', 'pbv': 'p/bv', 'div_yield': '%div.'}


def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    return 100 - 100 / (1 + gain / loss)


def pct_change(close, weeks):
    if len(close) <= weeks:
        return np.nan
    return (close.iloc[-1] / close.iloc[-1 - weeks] - 1) * 100


def compute_metrics(ticker, df):
    close = df['Close']
    last = close.iloc[-1]
    year = df.tail(52)
    high, low = year['High'].max(), year['Low'].min()
    weekly_returns = close.pct_change().tail(52)
    return {
        'ticker': ticker,
        'date': df.index[-1].date(),
        'close': last,
        'ret_1w': pct_change(close, 1),
        'ret_4w': pct_change(close, 4),
        'ret_13w': pct_change(close, 13),
        'ret_52w': pct_change(close, 52),
        'from_high_52w': (last / high - 1) * 100,
        'from_low_52w': (last / low - 1) * 100,
        'sma_10w': close.tail(10).mean() if len(close) >= 10 else np.nan,
        'sma_40w': close.tail(40).mean() if len(close) >= 40 else np.nan,
        'rsi_14': rsi(close).iloc[-1],
        # annualised from weekly returns
        'volatility': weekly_returns.std() * np.sqrt(52) * 100,
        'avg_volume': df['Volume'].tail(10).mean(),
        # average weekly traded value, million baht
        'avg_value_mb': (df['Close'] * df['Volume']).tail(10).mean() / 1e6,
    }


def load_metrics(data_dir=DATA_DIR):
    rows = []
    for path in sorted(glob.glob(os.path.join(data_dir, '*.csv'))):
        ticker = os.path.splitext(os.path.basename(path))[0]
        df = pd.read_csv(path, index_col='Date', parse_dates=True)
        df = df[df['Close'] > 0]
        # Drop weeks where Yahoo applied a split inconsistently. clean_prices needs
        # three weeks to judge a price, so a new listing is kept as it is
        if len(df) >= 3:
            df = df[clean_prices(df['Close']).notna()]
        if len(df) < 2:
            continue
        rows.append(compute_metrics(ticker, df))
    return pd.DataFrame(rows, columns=COLUMNS)


def load_symbols(path):
    """Market, kind and sector of each stock (data/market/symbols.csv)."""
    df = pd.read_csv(path)
    return df.rename(columns={'symbol': 'ticker'})[['ticker', 'market', 'kind', 'sector']]


def latest_snapshot(path=CONSENSUS_DIR):
    """A snapshot CSV, or the newest one when path is a folder."""
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, '*.csv')))
        if not files:
            raise SystemExit(f'No consensus snapshots in {path}; run consensus.py first')
        path = files[-1]
    return path


def load_consensus(path=CONSENSUS_DIR):
    df = pd.read_csv(latest_snapshot(path))
    picked = pick_columns(df)
    out = pd.DataFrame({
        'ticker': df['Symbol'],
        'median_target': picked.get('MedianTarget'),
        'upside': picked.get('Upside'),
        'analysts': picked.get('Analysts'),
        'rating': picked.get('Rating'),
    })
    lower = {c.strip().lower(): c for c in df.columns}
    for name, header in FUNDAMENTALS.items():
        out[name] = pd.to_numeric(df[lower[header]], errors='coerce') if header in lower else np.nan
    return out[['ticker'] + CONSENSUS_COLUMNS]


def screen(metrics, args):
    m = metrics
    if args.market:
        m = m[m['market'].str.lower() == args.market.lower()]
    if args.kind:
        m = m[m['kind'] == args.kind]
    if args.sector:
        m = m[m['sector'].fillna('').str.upper().isin({x.upper() for x in args.sector})]
    if args.min_value is not None:
        m = m[m['avg_value_mb'] >= args.min_value]
    if args.min_price is not None:
        m = m[m['close'] >= args.min_price]
    if args.max_price is not None:
        m = m[m['close'] <= args.max_price]
    if args.min_rsi is not None:
        m = m[m['rsi_14'] >= args.min_rsi]
    if args.max_rsi is not None:
        m = m[m['rsi_14'] <= args.max_rsi]
    if args.min_volume is not None:
        m = m[m['avg_volume'] >= args.min_volume]
    if args.min_ret_13w is not None:
        m = m[m['ret_13w'] >= args.min_ret_13w]
    if args.max_volatility is not None:
        m = m[m['volatility'] <= args.max_volatility]
    if args.near_high is not None:
        m = m[m['from_high_52w'] >= -args.near_high]
    if args.near_low is not None:
        m = m[m['from_low_52w'] <= args.near_low]
    for weeks in args.above_sma or []:
        m = m[m['close'] > m[f'sma_{weeks}w']]
    for weeks in args.below_sma or []:
        m = m[m['close'] < m[f'sma_{weeks}w']]
    if args.golden_cross:
        m = m[m['sma_10w'] > m['sma_40w']]
    if args.min_upside is not None:
        m = m[m['upside'] >= args.min_upside]
    if args.min_analysts is not None:
        m = m[m['analysts'] >= args.min_analysts]
    if args.rating:
        wanted = {r.lower() for r in args.rating}
        m = m[m['rating'].fillna('').str.lower().isin(wanted)]
    if args.max_pe is not None:
        m = m[(m['pe'] > 0) & (m['pe'] <= args.max_pe)]
    if args.max_pbv is not None:
        m = m[m['pbv'] <= args.max_pbv]
    if args.min_div is not None:
        m = m[m['div_yield'] >= args.min_div]
    m = m.sort_values(args.sort, ascending=args.asc, na_position='last')
    if args.top:
        m = m.head(args.top)
    return m


CONSENSUS_FILTERS = ('min_upside', 'min_analysts', 'rating', 'max_pe', 'max_pbv', 'min_div')
MARKET_FILTERS = ('market', 'kind', 'sector')


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--universe', choices=list(UNIVERSES), default='set100',
                   help='set100: data/ (default); all: every SET and mai stock in data/market/')
    p.add_argument('--data-dir', help='price folder (default: from --universe)')
    p.add_argument('--market', choices=['SET', 'mai'], type=lambda v: 'mai' if v.lower() == 'mai' else v.upper(),
                   help='SET or mai (needs --universe all)')
    p.add_argument('--kind', choices=['company', 'fund'],
                   help='company, or fund for property funds/REITs (needs --universe all)')
    p.add_argument('--sector', action='append', metavar='SECTOR',
                   help='SET sector code, e.g. BANK, ENERG, PF&REIT (repeatable; needs --universe all)')
    p.add_argument('--min-value', type=float, metavar='MB',
                   help='minimum average weekly traded value, million baht')
    p.add_argument('--min-price', type=float)
    p.add_argument('--max-price', type=float)
    p.add_argument('--min-rsi', type=float, help='minimum 14-week RSI')
    p.add_argument('--max-rsi', type=float, help='maximum 14-week RSI')
    p.add_argument('--min-volume', type=float, help='minimum 10-week average volume')
    p.add_argument('--min-ret-13w', type=float, help='minimum 13-week return, %%')
    p.add_argument('--max-volatility', type=float, help='maximum annualised volatility, %%')
    p.add_argument('--near-high', type=float, metavar='PCT',
                   help='within PCT %% of the 52-week high')
    p.add_argument('--near-low', type=float, metavar='PCT',
                   help='within PCT %% above the 52-week low')
    p.add_argument('--above-sma', type=int, choices=[10, 40], action='append',
                   help='close above the 10- or 40-week SMA (repeatable)')
    p.add_argument('--below-sma', type=int, choices=[10, 40], action='append',
                   help='close below the 10- or 40-week SMA (repeatable)')
    p.add_argument('--golden-cross', action='store_true', help='10-week SMA above 40-week SMA')
    p.add_argument('--consensus', nargs='?', const='', metavar='PATH',
                   help='merge 9hoon consensus: a snapshot CSV, or the newest in a folder '
                        '(default: the universe\'s consensus folder)')
    p.add_argument('--min-upside', type=float, help='minimum upside to the median target, %%')
    p.add_argument('--min-analysts', type=int, help='minimum number of covering analysts')
    p.add_argument('--rating', action='append', metavar='RATING',
                   help='keep this recommendation, e.g. Buy (repeatable)')
    p.add_argument('--max-pe', type=float, help='maximum trailing P/E (loss-makers dropped)')
    p.add_argument('--max-pbv', type=float, help='maximum P/BV')
    p.add_argument('--min-div', type=float, help='minimum dividend yield, %%')
    p.add_argument('--sort', default='ret_13w',
                   choices=COLUMNS[2:] + [c for c in CONSENSUS_COLUMNS if c != 'rating'])
    p.add_argument('--asc', action='store_true', help='sort ascending (default descending)')
    p.add_argument('--top', type=int, help='show only the first N results')
    p.add_argument('--csv', help='also save the result to this CSV file')
    args = p.parse_args(argv)
    uses_consensus = any(getattr(args, f) is not None for f in CONSENSUS_FILTERS) \
        or args.sort in CONSENSUS_COLUMNS
    if uses_consensus and args.consensus is None:
        p.error('consensus filters and sorts need --consensus')
    if args.universe != 'all' and any(getattr(args, f) for f in MARKET_FILTERS):
        p.error('--market, --kind and --sector need --universe all')
    price_dir, consensus_dir, args.symbols = UNIVERSES[args.universe]
    args.data_dir = args.data_dir or price_dir
    if args.consensus == '':
        # The market-wide snapshot is new; fall back to the SET100 one until it exists
        args.consensus = consensus_dir if glob.glob(os.path.join(consensus_dir, '*.csv')) else CONSENSUS_DIR
    return args


def main(argv=None):
    args = parse_args(argv)
    metrics = load_metrics(args.data_dir)
    if args.symbols:
        # Inner join drops files of stocks that have since been delisted
        metrics = load_symbols(args.symbols).merge(metrics, on='ticker')
    if args.consensus:
        metrics = metrics.merge(load_consensus(args.consensus), on='ticker', how='left')
    result = screen(metrics, args)
    if args.csv:
        result.to_csv(args.csv, index=False)
    if result.empty:
        print('No stocks matched.')
        return
    with pd.option_context('display.max_rows', None, 'display.width', 250,
                           'display.float_format', '{:,.2f}'.format):
        print(result.to_string(index=False))
    print(f'\n{len(result)} stocks matched.')


if __name__ == '__main__':
    main()
