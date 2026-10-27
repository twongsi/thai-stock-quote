import numpy as np
import pandas as pd
import pytest

import screener


def write_prices(folder, ticker, closes):
    dates = pd.date_range('2025-01-06', periods=len(closes), freq='W-MON')
    closes = np.asarray(closes, dtype=float)
    pd.DataFrame({'Date': dates, 'High': closes * 1.02, 'Low': closes * 0.98, 'Open': closes,
                  'Close': closes, 'Volume': 1e6, 'Adj Close': closes}).to_csv(
        folder / f'{ticker}.csv', index=False, date_format='%Y-%m-%d')


def write_snapshot(folder, date, rows):
    folder.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(folder / f'{date}.csv', index=False)


def hoon_row(sym, upside, cover, rating, pe, div):
    # Same headers as data/consensus/*.csv from 9hoon
    return {'SnapshotDate': 'x', 'Symbol': sym, 'Price': 10, 'P/E': pe, 'P/BV': 1.2, '%Div.': div,
            'Cover': cover, 'คำแนะนำ': rating, 'เป้าหมาย Median(บาท)': 10 * (1 + upside / 100),
            'Upside(จาก Median %)': upside, 'P/E 2569F(เท่า)': 99}


@pytest.fixture
def market(tmp_path):
    write_prices(tmp_path, 'UP', np.linspace(10, 20, 60))
    write_prices(tmp_path, 'DOWN', np.linspace(20, 10, 60))
    cons = tmp_path / 'consensus'
    write_snapshot(cons, '2026-10-01', [hoon_row('UP', 5, 10, 'Hold', 12, 2)])
    write_snapshot(cons, '2026-10-02', [hoon_row('UP', 25, 10, 'Buy', 12, 5),
                                        hoon_row('DOWN', 40, 2, 'Buy', -3, 0)])
    return tmp_path


def run(market, *argv):
    args = screener.parse_args(['--data-dir', str(market), *argv])
    m = screener.load_metrics(args.data_dir)
    if args.consensus:
        m = m.merge(screener.load_consensus(args.consensus), on='ticker', how='left')
    return screener.screen(m, args)


def test_technical_filters(market):
    m = screener.load_metrics(market).set_index('ticker')
    assert m.loc['UP', 'sma_10w'] > m.loc['UP', 'sma_40w']
    assert m.loc['UP', 'rsi_14'] > 70 and m.loc['DOWN', 'rsi_14'] < 30
    assert list(run(market, '--golden-cross')['ticker']) == ['UP']
    assert list(run(market, '--below-sma', '40')['ticker']) == ['DOWN']


def test_consensus_uses_newest_snapshot(market):
    c = screener.load_consensus(market / 'consensus').set_index('ticker')
    assert c.loc['UP', 'upside'] == 25 and c.loc['UP', 'rating'] == 'Buy'
    assert c.loc['UP', 'pe'] == 12 and c.loc['UP', 'div_yield'] == 5


def test_consensus_filters(market):
    cons = str(market / 'consensus')
    assert list(run(market, '--consensus', cons, '--min-upside', '20', '--sort', 'upside')['ticker']) == ['DOWN', 'UP']
    assert list(run(market, '--consensus', cons, '--min-analysts', '5')['ticker']) == ['UP']
    # negative P/E (a loss) never passes a P/E ceiling
    assert list(run(market, '--consensus', cons, '--max-pe', '15')['ticker']) == ['UP']
    assert list(run(market, '--consensus', cons, '--rating', 'buy', '--min-div', '4')['ticker']) == ['UP']


def test_consensus_filter_needs_flag(market):
    with pytest.raises(SystemExit):
        screener.parse_args(['--min-upside', '10'])


def test_universe_all_joins_symbols_and_filters_by_market(tmp_path):
    prices = tmp_path / 'market' / 'prices'
    prices.mkdir(parents=True)
    write_prices(prices, 'PTT', np.linspace(10, 20, 60))
    write_prices(prices, 'AU', np.linspace(10, 20, 60))
    write_prices(prices, 'CPNREIT', np.linspace(10, 20, 60))
    write_prices(prices, 'OLD', np.linspace(10, 20, 60))     # delisted: not in symbols.csv
    pd.DataFrame({'symbol': ['PTT', 'AU', 'CPNREIT'], 'market': ['SET', 'mai', 'SET'],
                  'kind': ['company', 'company', 'fund'], 'sector': ['ENERG', None, 'PF&REIT']}).to_csv(
        tmp_path / 'market' / 'symbols.csv', index=False)
    old = screener.UNIVERSES['all']
    screener.UNIVERSES['all'] = (str(prices), str(tmp_path / 'market' / 'consensus'),
                                 str(tmp_path / 'market' / 'symbols.csv'))
    try:
        def run_all(*argv):
            args = screener.parse_args(['--universe', 'all', *argv])
            m = screener.load_symbols(args.symbols).merge(screener.load_metrics(args.data_dir), on='ticker')
            return sorted(screener.screen(m, args)['ticker'])
        assert run_all() == ['AU', 'CPNREIT', 'PTT']
        assert run_all('--market', 'MAI') == ['AU']
        assert run_all('--market', 'set', '--kind', 'company') == ['PTT']
        assert run_all('--sector', 'pf&reit') == ['CPNREIT']
        assert run_all('--min-value', '1000') == []          # 1e6 shares x ~20 baht = ~20 MB a week
    finally:
        screener.UNIVERSES['all'] = old


def test_market_filters_need_universe_all():
    with pytest.raises(SystemExit):
        screener.parse_args(['--market', 'mai'])
