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
