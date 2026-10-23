import pandas as pd

from consensus import clean, pick_table

TICKERS = {'PTT', 'AOT', 'KBANK'}


def test_pick_table_chooses_table_with_most_tickers():
    nav = pd.DataFrame({'menu': ['Home', 'PTT']})
    data = pd.DataFrame({'Stock': ['PTT', 'AOT', 'KBANK'], 'Target': ['40', '70', '150']})
    df, col = pick_table([nav, data], TICKERS)
    assert df is data and col == 'Stock'


def test_clean_converts_numbers_but_keeps_text():
    df = pd.DataFrame({'Stock': [' ptt', 'AOT'], 'Target': ['1,300', '-'],
                       'Upside': ['13.0%', '5%'], 'Rating': ['BUY', 'HOLD']})
    out = clean(df, 'Stock')
    assert list(out['Symbol']) == ['PTT', 'AOT']
    assert out['Target'].iloc[0] == 1300 and pd.isna(out['Target'].iloc[1])
    assert list(out['Upside']) == [13.0, 5.0]
    assert list(out['Rating']) == ['BUY', 'HOLD']
