import csv
import requests
from bs4 import BeautifulSoup

URL = 'https://www.settrade.com/C13_MarketSummary.jsp?detail=SET100'

page = requests.get(URL)
soup = BeautifulSoup(page.content, 'html.parser')

def extract_ticker(s):
    try:
        no_front = s[60:]
        no_front_no_back = no_front.split('" ')[0]
        return no_front_no_back
    except:
        pass

tickers = []
for i in soup.find_all('a', class_='link-stt'):
    if 'txtSymbol' in str(i):
        ticker = extract_ticker(str(i))
        tickers.append(ticker)

with open('tickers.csv', mode='w') as file:
    writer = csv.writer(file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(tickers)

