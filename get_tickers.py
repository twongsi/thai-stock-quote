"""Download the SET100 constituents from the SET website and save to tickers.csv.

Uses the JSON endpoint behind https://www.set.or.th/en/market/index/set100/overview.
The old Settrade page (C13_MarketSummary.jsp) no longer exists. If the
request fails, tickers.csv is left unchanged.
"""
import csv
import sys

import requests

URL = 'https://www.set.or.th/api/set/index/set100/composition'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (thai-stock-quote research script)',
    'Accept': 'application/json',
    'Referer': 'https://www.set.or.th/en/market/index/set100/overview',
}


def extract_symbols(payload):
    """Collect 'symbol' values from every stockInfos list in the response."""
    symbols = []

    def walk(node):
        if isinstance(node, dict):
            for item in node.get('stockInfos') or []:
                if isinstance(item, dict) and item.get('symbol'):
                    symbols.append(item['symbol'].strip().upper())
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return sorted(set(symbols))


def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    # The API expects the cookies set by a normal page visit
    session.get(HEADERS['Referer'], timeout=30)
    resp = session.get(URL, params={'lang': 'en'}, timeout=30)
    resp.raise_for_status()
    tickers = extract_symbols(resp.json())
    if not 90 <= len(tickers) <= 110:
        sys.exit(f'expected about 100 symbols, got {len(tickers)}; tickers.csv not changed')

    with open('tickers.csv', mode='w', newline='') as file:
        csv.writer(file).writerow(tickers)
    print(f'saved {len(tickers)} tickers to tickers.csv')


if __name__ == '__main__':
    main()
