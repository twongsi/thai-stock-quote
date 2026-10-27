# RRG Studio · Sector Rotation

เครื่องมือ Relative Rotation Graph (RRG) และ workflow ทำ sector rotation สำหรับหุ้นไทย (SET), ดัชนีทั่วโลก, ETF และหุ้นสหรัฐฯ

- **RRG Studio** (`docs/index.html`) หน้าเว็บไฟล์เดียว เปิดในเบราว์เซอร์ได้เลย คำนวณทั้งหมดในเบราว์เซอร์ อัปโหลด CSV ของตัวเองได้
- **`sector_rotation.py`** pipeline ครบ 7 ขั้น: universe → data → ดัชนีหมวด → RRG และสมการความสัมพันธ์ → คะแนน → เลือกหมวด/หุ้น → backtest
- **GitHub Action** (`.github/workflows/rrg-weekly.yml` ที่ราก repo) ดึงราคาใหม่และสร้างหน้าใหม่ทุกวันเสาร์

รายละเอียดสมการ ผลทดสอบ และข้อควรระวังอยู่ใน [WORKFLOW.md](WORKFLOW.md)

## เริ่มใช้งาน

```bash
git clone https://github.com/twongsi/thai-stock-quote
cd thai-stock-quote/rrg             # ทุกคำสั่งรันจากโฟลเดอร์ rrg/
pip install -r requirements.txt     # pandas, numpy

# 1) ดึงราคาเอง → CSV (ไปอัปโหลดในหน้า RRG Studio ได้)
python fetch_prices.py --bench TDEX.BK --tickers PTT.BK AOT.BK CPALL.BK KBANK.BK --interval 1wk --out set.csv

# 2) สร้างหน้า RRG Studio ใหม่ด้วยข้อมูลล่าสุด
python build_data.py      # ดึงชุดข้อมูลทั้งหมด → data.json (ใช้เวลา 3–5 นาที)
python build_page.py      # รวม template + data → docs/index.html

# 3) รัน sector rotation + backtest
python sector_rotation.py --top 3 --rebalance 4 --cost 15 --out results
python sector_rotation.py --trend-filter --out results_trend
```

ใช้บน Google Colab ได้: อัปโหลดไฟล์ `.py` แล้วรันคำสั่งเดียวกันโดยใส่ `!` นำหน้า

## โครงสร้างไฟล์

| ไฟล์ | หน้าที่ | แก้ตรงไหนบ่อย |
|---|---|---|
| `fetch_prices.py` | ดึง adjusted close จาก Yahoo Finance, รวมแท่งรายสัปดาห์ | – |
| `build_data.py` | กำหนดชุดข้อมูลในหน้าเว็บ (`PRESETS`, `SET_SECTORS`, `SET_INDUSTRIES`, `WORLD`) | เพิ่ม/ลดหุ้นหรือดัชนี |
| `template.html` | หน้าเว็บ (HTML/CSS/JS) สูตร RRG ฝั่งเบราว์เซอร์อยู่ใน `compute()` | หน้าตา, สูตร, ข้อความ |
| `build_page.py` | ฝัง `data.json` และสคริปต์ลง template → `docs/index.html` | – |
| `sector_rotation.py` | workflow ครบ 7 ขั้น + backtest | `SET_SECTORS`, น้ำหนักใน `score()`, พารามิเตอร์ |
| `WORKFLOW.md` | เอกสารสมการ, ผลทดสอบ, ข้อควรระวัง | – |
| `tests/test_rrg.py` | unit test: ดัชนีหมวด, จตุภาค, backtest ไม่มองอนาคต (`pytest -q` ที่ราก repo) | – |
| `../.github/workflows/rrg-weekly.yml` | อัปเดตข้อมูลอัตโนมัติทุกสัปดาห์ | เวลา cron |

## พารามิเตอร์ของ `sector_rotation.py`

| ตัวเลือก | ค่าเริ่มต้น | ความหมาย |
|---|---|---|
| `--window` | 14 | จำนวนแท่งใน z-score ของ RS-Ratio และ RS-Momentum |
| `--top` | 3 | จำนวนหมวดที่ถือ |
| `--rebalance` | 4 | จำนวนสัปดาห์ต่อรอบปรับพอร์ต |
| `--cost` | 15 | ค่าธรรมเนียมรวม slippage ต่อข้าง (bps) |
| `--trend-filter` | ปิด | ตัดหมวดที่ราคาอยู่ใต้เส้นเฉลี่ย 40 สัปดาห์ |
| `--out` | results | โฟลเดอร์ผลลัพธ์: `snapshot.csv`, `metrics.csv`, `nav.csv`, `weights.csv`, `sector_index.csv` |

## รูปแบบ CSV สำหรับอัปโหลดในหน้าเว็บ

```
Date,TDEX.BK,PTT.BK,AOT.BK,CPALL.BK
2026-10-05,8.42,33.25,35.50,49.75
2026-10-12,8.51,33.75,36.25,50.25
```

คอลัมน์แรกเป็นวันที่ (`YYYY-MM-DD` หรือ `DD/MM/YYYY`, ปี พ.ศ. ได้) คอลัมน์ที่สองเป็น benchmark ที่เหลือคือตัวที่ต้องการเทียบ ข้อมูลรายวันจะถูกแปลงเป็นรายสัปดาห์ให้

## เปิดหน้าเว็บผ่าน GitHub Pages

Settings → Pages → Source: **GitHub Actions** แล้วกด *Run workflow* ที่ workflow **RRG weekly** ในแท็บ Actions
หน้าเว็บจะอยู่ที่ `https://twongsi.github.io/thai-stock-quote/`

หรือเปิดไฟล์ `rrg/docs/index.html` ในเบราว์เซอร์โดยตรงก็ได้ ไม่ต้องมีเซิร์ฟเวอร์

## อัปเดตข้อมูลอัตโนมัติ

`.github/workflows/rrg-weekly.yml` รันทุกวันเสาร์ 08:17 เวลาไทย หรือกด *Run workflow* ในแท็บ Actions
ขั้นตอน: ดึงราคา → สร้าง `rrg/docs/index.html` ใหม่ → รัน `sector_rotation.py` → commit ผลไว้ที่ `rrg/reports/latest/` → deploy GitHub Pages
schedule ทำงานเฉพาะบน branch หลัก (`main`) จึงเริ่มรันอัตโนมัติหลัง merge

## ข้อจำกัดที่ควรรู้

- **ดัชนีหมวด SET เป็น proxy** ตะกร้าหุ้นหลักถ่วงน้ำหนักเท่ากัน ไม่ใช่ดัชนีทางการ (ไม่มีแหล่งเปิดที่ให้ราคาย้อนหลังดัชนีหมวด) ถ้ามีข้อมูลจาก SETSMART ใส่เป็น CSV แทนได้
- **Benchmark ไทยใช้ TDEX.BK** (ETF อิง SET50) เพราะ Yahoo ไม่มีราคาย้อนหลังของ `^SET.BK`
- **ดัชนีทั่วโลกแปลงเป็น USD** แล้วเทียบ ACWI ผลจึงรวมผลของค่าเงิน
- **สูตร RS-Ratio / RS-Momentum เป็นสูตร z-score แบบเปิด** สูตร JdK ต้นฉบับไม่เปิดเผย ค่าจึงใกล้เคียงแต่ไม่เท่ากับ Bloomberg หรือ StockCharts
- **Backtest มี survivorship bias** เพราะใช้รายชื่อหุ้นปัจจุบันย้อนหลัง ผลส่วนใหญ่มาจากหมวด ETRON ดู [WORKFLOW.md](WORKFLOW.md) ก่อนนำไปใช้
- ราคาไทยจาก Yahoo มีจุดผิดพลาดเรื่องการแตกพาร์และการปรับราคา `analytics.py` ของ repo นี้มีฟังก์ชัน `clean_prices` สำหรับซ่อมแล้ว แต่โฟลเดอร์ `rrg/` ยังไม่ได้ใช้
- Yahoo Finance เป็นแหล่งข้อมูลไม่เป็นทางการ อาจเปลี่ยนรูปแบบหรือจำกัดการเรียกได้

เพื่อการศึกษาและวิจัย ไม่ใช่คำแนะนำการลงทุน
