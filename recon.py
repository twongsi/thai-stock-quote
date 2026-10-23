"""Map how a web page delivers its data before writing a scraper for it.

Accepts a URL, a saved .html file, or a .har file exported from the browser
DevTools Network tab, and reports tables, forms, scripts and anything that
looks like a data endpoint.

    python recon.py https://9hoon.com/aset/view_analyst_consensus.php
    python recon.py saved_page.html
    python recon.py capture.har
"""
import argparse
import json
import os
import re
import sys
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

USER_AGENT = 'Mozilla/5.0 (thai-stock-quote research script)'
ENDPOINT_RE = re.compile(r'''["']([^"'\s]+?\.(?:php|json|jsp|aspx|csv)(?:\?[^"'\s]*)?)["']''')
API_RE = re.compile(r'''["']((?:https?:)?/[^"'\s]*(?:api|ajax|data|json)[^"'\s]*)["']''', re.I)


def robots_allowed(url):
    parts = urlparse(url)
    rp = RobotFileParser(f'{parts.scheme}://{parts.netloc}/robots.txt')
    try:
        rp.read()
    except Exception:
        return None
    return rp.can_fetch(USER_AGENT, url)


def fetch(url, out_dir):
    allowed = robots_allowed(url)
    print(f'robots.txt allows fetch: {allowed}')
    if allowed is False:
        sys.exit('robots.txt disallows this URL; stopping.')
    resp = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=30)
    print(f'HTTP {resp.status_code}  {resp.headers.get("Content-Type")}  {len(resp.content)} bytes')
    for h in ('Server', 'Set-Cookie', 'X-Powered-By', 'Cache-Control'):
        if h in resp.headers:
            print(f'  {h}: {resp.headers[h]}')
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, (urlparse(url).path.strip('/').replace('/', '_') or 'index') + '.html')
    with open(path, 'wb') as f:
        f.write(resp.content)
    print(f'saved raw HTML -> {path}')
    resp.encoding = resp.apparent_encoding
    return resp.text, url


def report_html(html, base_url=''):
    soup = BeautifulSoup(html, 'html.parser')
    print(f'\ntitle: {soup.title.string.strip() if soup.title and soup.title.string else None}')

    tables = soup.find_all('table')
    print(f'\n== tables: {len(tables)}')
    for i, t in enumerate(tables):
        rows = t.find_all('tr')
        header = rows[0].find_all(['th', 'td']) if rows else []
        print(f'[{i}] id={t.get("id")} class={t.get("class")} rows={len(rows)}')
        print('    header:', [c.get_text(' ', strip=True) for c in header])
        if len(rows) > 1:
            print('    row 1: ', [c.get_text(' ', strip=True) for c in rows[1].find_all(['th', 'td'])])

    forms = soup.find_all('form')
    print(f'\n== forms: {len(forms)}')
    for f in forms:
        print(f'  {f.get("method", "GET").upper()} {urljoin(base_url, f.get("action", ""))}')
        for inp in f.find_all(['input', 'select', 'textarea']):
            opts = [o.get('value', o.get_text(strip=True)) for o in inp.find_all('option')][:10]
            print(f'    {inp.name} name={inp.get("name")} type={inp.get("type")} value={inp.get("value")}'
                  + (f' options={opts}' if opts else ''))

    print('\n== scripts')
    inline = []
    for s in soup.find_all('script'):
        if s.get('src'):
            print('  src:', urljoin(base_url, s['src']))
        elif s.string:
            inline.append(s.string)
    print(f'  inline scripts: {len(inline)}')

    candidates = set()
    for text in inline + [html]:
        candidates.update(ENDPOINT_RE.findall(text))
        candidates.update(API_RE.findall(text))
    for a in soup.find_all(['a', 'iframe'], href=True) + soup.find_all('iframe', src=True):
        link = a.get('href') or a.get('src')
        if '?' in link:
            candidates.add(link)
    print(f'\n== candidate data endpoints / parameterised links: {len(candidates)}')
    for c in sorted(candidates)[:100]:
        print('  ', urljoin(base_url, c))


def report_har(path):
    with open(path, encoding='utf-8') as f:
        entries = json.load(f)['log']['entries']
    print(f'== HAR entries: {len(entries)}')
    for e in entries:
        req, res = e['request'], e['response']
        mime = res.get('content', {}).get('mimeType', '')
        if any(k in mime for k in ('json', 'html', 'csv', 'javascript', 'protobuf', 'octet')):
            print(f'{req["method"]:6} {res["status"]} {mime[:30]:30} {req["url"][:150]}')
            if req.get('postData'):
                print('       body:', req['postData'].get('text', '')[:200])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('target', help='URL, .html file or .har file')
    ap.add_argument('--out', default='recon', help='folder for the saved raw HTML')
    args = ap.parse_args()

    if args.target.endswith('.har'):
        report_har(args.target)
    elif args.target.startswith('http'):
        html, base = fetch(args.target, args.out)
        report_html(html, base)
    else:
        with open(args.target, encoding='utf-8', errors='replace') as f:
            report_html(f.read())


if __name__ == '__main__':
    main()
