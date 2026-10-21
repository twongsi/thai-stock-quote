"""Download analyst consensus (target prices and ratings) for each ticker from Yahoo.

Saves one row per ticker to consensus.csv, which screener.py can merge with --consensus.

Examples:
    python analyst_consensus.py
    python analyst_consensus.py --sort analysts --top 20
"""
import argparse
import csv

import pandas as pd
import yfinance as yf
from tqdm import tqdm

OUTPUT = 'consensus.csv'

COLUMNS = ['ticker', 'price', 'target_mean', 'target_median', 'target_high', 'target_low',
           'upside', 'analysts', 'rating', 'rating_score',
           'strong_buy', 'buy', 'hold', 'sell', 'strong_sell']

RATING_COUNTS = {'strong_buy': 'strongBuy', 'buy': 'buy', 'hold': 'hold',
                 'sell': 'sell', 'strong_sell': 'strongSell'}


def read_tickers(path='tickers.csv'):
    with open(path, newline='') as f:
        return list(csv.reader(f))[0]


def fetch_consensus(ticker):
    t = yf.Ticker(ticker + '.BK')
    info = t.info
    price = info.get('currentPrice') or info.get('regularMarketPrice')
    target = info.get('targetMeanPrice')
    row = {
        'ticker': ticker,
        'price': price,
        'target_mean': target,
        'target_median': info.get('targetMedianPrice'),
        'target_high': info.get('targetHighPrice'),
        'target_low': info.get('targetLowPrice'),
        'upside': (target / price - 1) * 100 if price and target else None,
        'analysts': info.get('numberOfAnalystOpinions'),
        'rating': info.get('recommendationKey'),
        # 1 = strong buy ... 5 = strong sell
        'rating_score': info.get('recommendationMean'),
    }
    summary = t.recommendations_summary
    if summary is not None and not summary.empty:
        current = summary[summary['period'] == '0m']
        current = current.iloc[0] if not current.empty else summary.iloc[0]
        for col, key in RATING_COUNTS.items():
            row[col] = current.get(key)
    return row


def load_consensus(tickers):
    rows = []
    for ticker in tqdm(tickers):
        try:
            rows.append(fetch_consensus(ticker))
        except Exception as e:
            tqdm.write(f'{ticker}: {e}')
    return pd.DataFrame(rows, columns=COLUMNS)


def parse_args():
    p = argparse.ArgumentParser(description='Download analyst consensus for SET100 stocks')
    p.add_argument('--tickers', default='tickers.csv')
    p.add_argument('--output', default=OUTPUT)
    p.add_argument('--sort', default='upside', choices=COLUMNS[1:])
    p.add_argument('--asc', action='store_true', help='sort ascending (default descending)')
    p.add_argument('--top', type=int, help='show only the first N results')
    return p.parse_args()


def main():
    args = parse_args()
    result = load_consensus(read_tickers(args.tickers))
    result = result.sort_values(args.sort, ascending=args.asc, na_position='last')
    result.to_csv(args.output, index=False)
    shown = result.head(args.top) if args.top else result
    with pd.option_context('display.max_rows', None, 'display.width', 200,
                           'display.float_format', '{:,.2f}'.format):
        print(shown.to_string(index=False))
    covered = result['target_mean'].notna().sum()
    print(f'\n{covered} of {len(result)} stocks have a target price. Saved to {args.output}')


if __name__ == '__main__':
    main()
