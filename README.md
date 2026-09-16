# thai-stock-quote

เครื่องมือดึงข้อมูลตลาดทุนไทยไว้ใช้วิเคราะห์เอง

## Thai Fund Dashboard (ใหม่) — `fund_dashboard/`

Dashboard กองทุนรวมไทยครบจบในหน้าเดียว ดึงข้อมูลจาก **SEC Open Data API (v2)**:
NAV ล่าสุด, ผลตอบแทนทุกช่วงเวลา, ค่าความเสี่ยง, กราฟ NAV ย้อนหลัง, พอร์ตการลงทุน,
ค่าธรรมเนียม และเปรียบเทียบหลายกองทุนบนกราฟเดียวกัน

```bash
cd fund_dashboard
cp .env.example .env     # ใส่ SEC_API_KEY ที่ขอจาก https://secopendata.sec.or.th/
python3 server.py        # เปิด http://127.0.0.1:8765
python3 server.py --demo # ลองดูหน้าตาก่อนโดยไม่ต้องใช้ API Key
```

ใช้ Python standard library ล้วน ไม่ต้องติดตั้ง package เพิ่ม — รายละเอียดทั้งหมดอยู่ใน
[fund_dashboard/README.md](fund_dashboard/README.md)

## สคริปต์ข้อมูลหุ้น (ของเดิม)

- `get_tickers.py` — ดึงรายชื่อหุ้น SET100 จาก Settrade เก็บลง `tickers.csv`
- `download.py` — ดึงราคาย้อนหลังของแต่ละตัวจาก Yahoo Finance เก็บลง `data/`
