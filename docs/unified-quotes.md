# หุ้นและกองทุนจากบริการเดียว

บริการ Python เดิมรองรับ `/api/quote` และ `/api/history` เพิ่มเติม โดยอ่านหุ้นจาก
CSV ใน repository และอ่าน NAV ผ่าน SEC client ที่เลือกได้ คำขอหุ้นไม่ต้องใช้ SEC key

## ใช้ fork ที่ตรึงเวอร์ชัน

- Repository: https://github.com/twongsi/sec-go
- Commit: `50360dba6ec87f74ae82a59541d1b57537ae545a`
- Go version: `v0.0.0-20260713122606-50360dba6ec8`
- Lock: `tools/sec-bridge/sec-go.lock.json`, `go.mod`, `go.sum`

fork ยังประกาศ module path เป็น `github.com/jwitmann/sec-go` จึงใช้ Go `replace`
ให้ดาวน์โหลดจาก **twongsi/sec-go ที่ commit ข้างต้น** โดยไม่แก้ source ของ dependency
หรือดึง `main`/`latest` ทุกครั้ง Python ตรวจ build metadata ของ binary ให้ตรงกับ lock
ก่อนใช้งาน ถ้าเปลี่ยน lock ต้อง update go.mod/go.sum และ rebuild ด้วย

ติดตั้ง Go 1.25.0 ขึ้นไป แล้วรันจาก root ของ repository:

```bash
cd tools/sec-bridge
go mod verify
go test ./...
go build -trimpath -o ../../bin/sec-bridge .
cd ../..
bin/sec-bridge --version
```

คัดลอก `fund_dashboard/.env.example` เป็น `fund_dashboard/.env` แล้วใส่ SEC key
และเปลี่ยน `SEC_BACKEND=sec-go` (ใช้ `python` เพื่อใช้ standard-library client เดิม)
key ส่งให้ Go ทาง environment เท่านั้น ไม่อยู่ใน command-line arguments, URL หรือเว็บ

```bash
python3 fund_dashboard/probe_sec.py
python3 fund_dashboard/server.py
```

## ตัวอย่างเรียก

```bash
curl 'http://127.0.0.1:8765/api/quote?asset_type=stock&symbol=PTT'
curl 'http://127.0.0.1:8765/api/quote?asset_type=fund&symbol=SCBNDQ(A)'
curl 'http://127.0.0.1:8765/api/history?asset_type=stock&symbol=PTT&start=2025-01-01'
curl 'http://127.0.0.1:8765/api/history?asset_type=fund&symbol=SCBNDQ(A)&years=3'
```

ผลลัพธ์ร่วมมี `asset_type`, `symbol`, `price`, `price_type`, `as_of`, `interval`,
`source`, `is_realtime`, `is_demo`, `age_days`, `served_at` และ `currency`
`/api/history` เพิ่ม `history` ซึ่งเป็นรายการ `{date, price}`

หุ้นเป็น **Close ของแท่งรายสัปดาห์ที่เก็บไว้** วันที่คือวันเริ่มแท่งตาม CSV
(`date_semantics=bar_start_date`) ไม่ใช่เวลาซื้อขายล่าสุด ส่วนกองทุนเป็น NAV รายวัน
(`date_semantics=nav_date`) ต้องใช้รหัสชนิดหน่วยลงทุนให้ถูกต้อง ไม่มีการรวม NAV หลาย class
ค่า `currency` ของกองทุนเป็น null เพราะ NAV endpoint ไม่ระบุสกุลเงิน ต้องตรวจ factsheet
`age_days` คำนวณจากวันที่ข้อมูล ไม่ใช่อายุ cache หรือวันที่ดาวน์โหลด

การกรอง `start`/`end` ใช้วันที่ข้อมูลแบบ inclusive; `years` จำกัดช่วงที่ดึง NAV (1–20 ปี)
หุ้นอ่านประวัติที่มีใน CSV และไม่ใช้ `years` จำกัดข้อมูล
ระบบไม่แปลงความถี่หรือคำนวณผลตอบแทนรวมข้ามสินทรัพย์ให้โดยอัตโนมัติ

รหัสที่ไม่พบ/ไม่มีข้อมูลคืน 404; query ไม่ถูกต้องคืน 400; upstream มีปัญหาคืน 502
endpoint กองทุนเดิมยังคงรูปแบบตอบกลับเดิมเพื่อรักษาความเข้ากันได้

## GitHub Pages และการตรวจข้อมูลจริง

GitHub Pages เสิร์ฟไฟล์ static เท่านั้น `/api/*` ต้องรัน Python server บนเครื่องหรือ backend host
workflow `fund-dashboard.yml` ใช้ Go bridge ที่ตรึงเวอร์ชันดึงข้อมูล แล้วสร้างไฟล์ JSON สำหรับ Pages
หุ้นและ RRG เดิมยังใช้ pipeline เดิม

workflow ตรวจคำตอบจริงด้วย `probe_sec.py` ก่อน build โดยแสดงเฉพาะ endpoint,
HTTP status, Content-Type, จำนวน byte และจำนวนแถว ไม่แสดง API key หรือ response body
HTTP 204 ถือว่าไม่มีข้อมูล; HTTP 200 ที่ body ว่าง/HTML/JSON ผิดรูปแบบถือว่าไม่ผ่าน
pagination ต้องอ่านครบ หยุดพร้อม error เมื่อ cursor ซ้ำหรือเกินขีดจำกัด

ถ้าไม่มี key, NAV ว่าง หรือกองใด build ไม่สำเร็จ จะไม่ deploy ทับเว็บเดิม
เลือกข้อมูลจำลองได้เฉพาะ manual workflow input `demo=true`; ข้อมูลจะมี `demo=true`
การรัน branch `codex/unified-quotes-pinned-sec-go` ใช้สำหรับตรวจด้วย secret ของ repository
แต่จะไม่ deploy Pages; เฉพาะ `main` เท่านั้นที่ deploy ได้

การทดสอบ offline ผ่านไม่ได้ยืนยันว่า SEC key หรือข้อมูลจริงใช้งานได้ ต้องตรวจ log ของ live workflow
และวันที่ NAV หลัง merge ก่อนถือว่าพร้อมใช้งาน

## ทดสอบ

```bash
python3 -m pytest -q
python3 fund_dashboard/selftest.py --demo
```

เมื่อ build binary แล้ว tests จะใช้ local HTTP server ทดสอบทั้ง Python และ Go
ครอบคลุม HTTP 204, HTML, body ว่าง, auth errors, retry, pagination, cache และ revision lock
CI มี job แยกสำหรับ build/test Go bridge และทดสอบทั้งสอง transport

## License

SEC-Go ใช้ MIT License เก็บสำเนาไว้ที่ `tools/sec-bridge/LICENSE.sec-go`
และต้นฉบับที่ commit ที่ตรึงไว้:
https://github.com/twongsi/sec-go/blob/50360dba6ec87f74ae82a59541d1b57537ae545a/LICENSE
