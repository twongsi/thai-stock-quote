# thai-stock-quote

get_tickers.py -> download ticker symbol of each stock in SET100 from Settrade, save to tickers.csv

download.py -> download quote of each ticker symbol from Yahoo

recon.py -> map how a web page delivers its data (tables, forms, JS endpoints, HAR captures) before writing a scraper

consensus.py -> snapshot the analyst-consensus table from 9hoon.com (aset) for SET100 tickers, save to data/consensus/YYYY-MM-DD.csv

See docs/reverse-engineering-data-sources.md for the workflow and tools.
