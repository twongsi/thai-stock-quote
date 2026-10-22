# Reverse-engineering Thai market data sources

How to work out where a web page gets its numbers, so a scraper can read the
cleanest source (often a JSON endpoint behind the HTML). The tools are from the
"Web and protocols" section of
[awesome-reverse-engineering](https://github.com/twongsi/awesome-reverse-engineering#web-and-protocols).

Worked target: analyst consensus at
<https://9hoon.com/aset/view_analyst_consensus.php>.

## Before you start

- Read the site's terms of use and `robots.txt` (`recon.py` checks robots.txt for you).
- Fetch slowly, for personal research only, and don't redistribute the data.
- Don't get around logins, paywalls or rate limits.

## Workflow

| Step | Question | Tool |
| --- | --- | --- |
| 1. Static triage | Is the table in the HTML, or loaded later by JavaScript? | `python recon.py <url>` |
| 2. Live traffic | Which requests fill the page (XHR/fetch, POST forms, WebSocket)? | [Chrome DevTools](https://developer.chrome.com/docs/devtools/) → Network → filter Fetch/XHR, then *Save all as HAR* |
| 3. Read the capture | Which endpoint returns the data, and with which parameters? | `python recon.py capture.har` |
| 4. Replay and vary | What do the parameters do (sector, date, page)? Are cookies or tokens needed? | DevTools *Copy as cURL*, [mitmproxy](https://github.com/mitmproxy/mitmproxy), [Burp Suite](https://portswigger.net/burp) Community or [HTTP Toolkit](https://httptoolkit.com/) |
| 5. Read obfuscated JS | How is a request signed or a response decoded? | [webcrack](https://github.com/j4k0xb/webcrack), DevTools breakpoints |
| 6. Binary payloads | Is the response Protobuf or another binary format? | [Protobuf Decoder](https://github.com/pawitp/protobuf-decoder) |
| 7. Mobile apps | Does the broker app call an API the website doesn't? | HTTP Toolkit or mitmproxy with an Android device |

## Deciding how to scrape

- **The table is in the HTML** (`recon.py` shows the table and its header):
  `consensus.py` reads it directly with `pandas.read_html`.
- **The page loads a `.php`/JSON endpoint**: call that endpoint with `requests`
  and build the DataFrame from the JSON. It's faster and won't break when the
  page layout changes.
- **The data only appears after JavaScript runs and the endpoint is hard to
  replay**: use Playwright to render the page, then pass the HTML to
  `consensus.py --source page.html`.

## Commands

```bash
python recon.py https://9hoon.com/aset/view_analyst_consensus.php   # saves recon/*.html
python consensus.py                                                 # -> data/consensus/YYYY-MM-DD.csv
python consensus.py --source recon/aset_view_analyst_consensus.php.html --table 1
```

Running `consensus.py` once a day builds a history of target-price snapshots. You
can join it with the weekly prices in `data/<TICKER>.csv` to study how target
prices change over time and how far the price is from target.
