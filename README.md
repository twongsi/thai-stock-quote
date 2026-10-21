# thai-stock-quote

get_tickers.py -> download ticker symbol of each stock in SET100 from Settrade, save to tickers.csv

download.py -> download quote of each ticker symbol from Yahoo

screener.py -> screen the downloaded quotes by price, return, RSI, moving averages, 52-week high/low, volatility and volume

```
python screener.py                                    # all stocks, sorted by 13-week return
python screener.py --min-rsi 50 --above-sma 40 --golden-cross --near-high 5
python screener.py --near-low 10 --sort ret_52w --asc --top 10 --csv result.csv
python screener.py -h                                 # all filters
```

All indicators are weekly: `sma_10w`/`sma_40w` are roughly the 50/200-day averages, `rsi_14` is a 14-week RSI, `volatility` is annualised from the last 52 weekly returns and `avg_volume` is the 10-week average.

analyst_consensus.py -> download analyst consensus (mean/median/high/low target price, upside, analyst count, rating and buy/hold/sell counts) of each ticker from Yahoo, save to consensus.csv (needs `pip install yfinance`)

```
python analyst_consensus.py --top 20                  # sorted by upside to the mean target
python screener.py --consensus --min-upside 15 --min-analysts 5 --above-sma 40 --sort upside
```

`rating_score` runs from 1 (strong buy) to 5 (strong sell); `--max-rating-score 2` keeps buy-rated stocks. `upside` uses Yahoo's current price, so refresh `data/` with download.py before mixing it with the technical filters.

test_sources.py -> check which SET data sources (Yahoo via yfinance, Settrade JSON API, set.or.th) are reachable from your network: `python test_sources.py PTT`
