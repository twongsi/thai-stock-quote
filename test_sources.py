"""Check which SET data sources are reachable and what each one returns.

Run it when download.py or consensus.py starts failing, to see which source is down.

    python test_sources.py            # tests PTT
    python test_sources.py ADVANC
"""
import sys

import requests

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else 'PTT'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36')


def check(name, fn):
    try:
        print(f'[OK]   {name}: {fn()}')
    except Exception as e:
        print(f'[FAIL] {name}: {type(e).__name__}: {e}')


def yahoo_history():
    import yfinance as yf
    df = yf.Ticker(SYMBOL + '.BK').history(period='1mo')
    last = df.iloc[-1]
    return f'{len(df)} rows, last {df.index[-1].date()} close {last["Close"]:.2f}'


def yahoo_consensus():
    import yfinance as yf
    info = yf.Ticker(SYMBOL + '.BK').info
    return (f'P/E {info.get("trailingPE")}, P/BV {info.get("priceToBook")}, '
            f'yield {info.get("dividendYield")}, target {info.get("targetMeanPrice")}, '
            f'analysts {info.get("numberOfAnalystOpinions")}')


def settrade_financials():
    # Same flow as the set-mcp package: open the quote page for cookies, then call the JSON API
    s = requests.Session()
    s.headers['user-agent'] = UA
    page = f'https://www.settrade.com/th/equities/quote/{SYMBOL}/financial-statement/full'
    s.get(page, timeout=20).raise_for_status()
    r = s.get(f'https://www.settrade.com/api/set/stock/{SYMBOL}/financialstatement',
              params={'accountType': 'income_statement', 'fsType': 'company',
                      'period': 'Q4', 'language': 'en'},
              headers={'accept': 'application/json', 'referer': page}, timeout=20)
    r.raise_for_status()
    return f'{len(r.json().get("accounts", []))} income statement lines'


def hoon_consensus():
    import pandas as pd
    from io import StringIO
    r = requests.get('https://9hoon.com/aset/view_analyst_consensus.php',
                     headers={'user-agent': UA}, timeout=30)
    r.raise_for_status()
    rows = max(len(t) for t in pd.read_html(StringIO(r.text)))
    return f'HTTP {r.status_code}, largest table {rows} rows'


def set_website():
    r = requests.get(f'https://www.set.or.th/th/market/product/stock/quote/{SYMBOL}/price',
                     headers={'user-agent': UA}, timeout=20)
    r.raise_for_status()
    return f'HTTP {r.status_code}, {len(r.text):,} bytes'


if __name__ == '__main__':
    check('Yahoo price history (yfinance)', yahoo_history)
    check('Yahoo fundamentals + consensus (yfinance)', yahoo_consensus)
    check('9hoon analyst consensus table', hoon_consensus)
    check('Settrade financial statement API', settrade_financials)
    check('set.or.th quote page', set_website)
