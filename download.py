import csv
import pandas as pd
import pandas_datareader.data as web
from tqdm import tqdm

start_date = '01/01/2010'

with open('tickers.csv', newline='') as f:
    file = csv.reader(f)
    tickers = list(file)[0]

for ticker in tqdm(tickers):
    full_ticker = ticker + '.BK'
    data = web.get_data_yahoo(full_ticker, start_date, interval='w')
    save_path = 'data/' + ticker + '.csv'
    data.to_csv(save_path)


