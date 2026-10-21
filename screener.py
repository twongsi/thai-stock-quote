"""Technical stock screener for the weekly quotes saved by download.py.

Examples:
    python screener.py
    python screener.py --min-rsi 50 --above-sma 40 --sort ret_13w
    python screener.py --near-high 5 --min-volume 10000000 --top 10 --csv out.csv
    python screener.py --consensus --min-upside 15 --min-analysts 5 --sort upside
"""
import argparse
import glob
import os

import numpy as np
import pandas as pd

DATA_DIR = 'data'
CONSENSUS_COLUMNS = ['target_mean', 'upside', 'analysts', 'rating', 'rating_score']

COLUMNS = ['ticker', 'date', 'close', 'ret_1w', 'ret_4w', 'ret_13w', 'ret_52w',
           'from_high_52w', 'from_low_52w', 'sma_10w', 'sma_40w', 'rsi_14',
           'volatility', 'avg_volume']


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
    df = df.dropna(subset=['Close'])
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
    }


def load_metrics(data_dir=DATA_DIR):
    rows = []
    for path in sorted(glob.glob(os.path.join(data_dir, '*.csv'))):
        ticker = os.path.splitext(os.path.basename(path))[0]
        df = pd.read_csv(path, index_col='Date', parse_dates=True)
        if len(df) < 2:
            continue
        rows.append(compute_metrics(ticker, df))
    return pd.DataFrame(rows, columns=COLUMNS)


def add_consensus(metrics, path):
    consensus = pd.read_csv(path, usecols=['ticker'] + CONSENSUS_COLUMNS)
    return metrics.merge(consensus, on='ticker', how='left')


def screen(metrics, args):
    m = metrics
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
    if args.max_rating_score is not None:
        m = m[m['rating_score'] <= args.max_rating_score]
    m = m.sort_values(args.sort, ascending=args.asc, na_position='last')
    if args.top:
        m = m.head(args.top)
    return m


def parse_args():
    p = argparse.ArgumentParser(description='Screen SET100 stocks from weekly quotes in data/')
    p.add_argument('--data-dir', default=DATA_DIR)
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
    p.add_argument('--consensus', nargs='?', const='consensus.csv', metavar='FILE',
                   help='merge analyst consensus from analyst_consensus.py (default consensus.csv)')
    p.add_argument('--min-upside', type=float,
                   help='minimum upside to the mean target price, %% (needs --consensus)')
    p.add_argument('--min-analysts', type=int, help='minimum analyst count (needs --consensus)')
    p.add_argument('--max-rating-score', type=float,
                   help='maximum mean rating, 1 = strong buy .. 5 = strong sell (needs --consensus)')
    p.add_argument('--sort', default='ret_13w',
                   choices=COLUMNS[2:] + [c for c in CONSENSUS_COLUMNS if c != 'rating'])
    p.add_argument('--asc', action='store_true', help='sort ascending (default descending)')
    p.add_argument('--top', type=int, help='show only the first N results')
    p.add_argument('--csv', help='also save the result to this CSV file')
    return p.parse_args()


def main():
    args = parse_args()
    needs_consensus = (args.min_upside, args.min_analysts, args.max_rating_score)
    if args.consensus is None and (any(v is not None for v in needs_consensus)
                                   or args.sort in CONSENSUS_COLUMNS):
        raise SystemExit('Consensus filters and sorts need --consensus')
    metrics = load_metrics(args.data_dir)
    if args.consensus:
        metrics = add_consensus(metrics, args.consensus)
    result = screen(metrics, args)
    if args.csv:
        result.to_csv(args.csv, index=False)
    if result.empty:
        print('No stocks matched.')
        return
    with pd.option_context('display.max_rows', None, 'display.width', 200,
                           'display.float_format', '{:,.2f}'.format):
        print(result.to_string(index=False))
    print(f'\n{len(result)} stocks matched.')


if __name__ == '__main__':
    main()
