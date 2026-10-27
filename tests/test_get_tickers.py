from get_tickers import extract_symbols


def test_extract_symbols_walks_nested_stock_infos():
    payload = {'composition': {'stockInfos': [{'symbol': 'ptt '}, {'symbol': 'AOT'}],
                               'subIndices': [{'stockInfos': [{'symbol': 'AOT'}, {'name': 'x'}]}]}}
    assert extract_symbols(payload) == ['AOT', 'PTT']
