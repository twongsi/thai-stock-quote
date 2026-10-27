"""ประกอบหน้า rrg-studio.html จาก template.html + data.json + fetch_prices.py"""
import html, os
t = open("template.html").read()
t = t.replace("/*DATA*/", open("data.json").read()).replace("/*SCRIPT*/", html.escape(open("fetch_prices.py").read()))
open("rrg-studio.html", "w").write(t)  # สำหรับ Claude Artifact (ไม่มี <html> wrapper)
# สำหรับ GitHub Pages / เปิดในเบราว์เซอร์โดยตรง
os.makedirs("docs", exist_ok=True)
open("docs/index.html", "w").write('<!doctype html>\n<html lang="th"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
    '<style>[hidden]{display:none!important}body{margin:0}</style></head><body>\n' + t + '\n</body></html>\n')
print("rrg-studio.html + docs/index.html", len(t)//1024, "KB")
