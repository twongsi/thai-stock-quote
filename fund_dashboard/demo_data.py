"""โหมดสาธิต — จำลองข้อมูลแบบเดียวกับที่ SEC Open API ส่งกลับมา

มีไว้เพื่อ 2 อย่าง
  1) ลอง dashboard ได้ทันทีระหว่างรอ API Key จาก SEC
  2) ใช้เป็นตัวอย่างโครงสร้างข้อมูลของแต่ละ endpoint

ตัวเลขทั้งหมดในไฟล์นี้เป็นข้อมูลจำลอง (สุ่มแบบ seed คงที่) ไม่ใช่ข้อมูลจริงของกองทุน
ห้ามนำไปใช้ตัดสินใจลงทุน
"""

from __future__ import annotations

import hashlib
import random
from datetime import date, timedelta

# proj_id, code, ชื่อไทย, ชื่ออังกฤษ, บลจ., นโยบาย, class, risk, วันจดทะเบียน, drift/ปี, vol/ปี
DEMO_FUNDS = [
    {
        "proj_id": "M0311_2564",
        "target_total": 0.665,
        "code": "SCBNDQ",
        "name_th": "กองทุนเปิดไทยพาณิชย์ หุ้นยูเอส เอ็นดีคิว",
        "name_en": "SCB US Equity NDQ",
        "amc_th": "บริษัทหลักทรัพย์จัดการกองทุน ไทยพาณิชย์ จำกัด",
        "amc_en": "SCB ASSET MANAGEMENT COMPANY LIMITED",
        "unique_id": "C0000000031",
        "policy": "ตราสารทุน",
        "classes": ["SCBNDQ(A)", "SCBNDQ(D)", "SCBNDQ(E)", "SCBNDQ(IN)", "SCBNDQ(P)", "SCBNDQ(R)", "SCBNDQ(SSF)", "SCBNDQ(SSFE)"],
        "risk": "RS6",
        "risk_desc": "ลงทุนในตราสารทุนเป็นหลัก โดยเฉลี่ยในรอบปีไม่น้อยกว่า 80% ของ NAV",
        "regis_date": "2021-08-11",
        "drift": 0.19,
        "vol": 0.20,
        "nav0": 10.0,
        "net_asset": 8_258_000_000,
        "feeder": "Invesco QQQ Trust Series 1",
        "feeder_country": "United States of America",
        "fx": "ป้องกันความเสี่ยงจากอัตราแลกเปลี่ยนทั้งจำนวน",
        "dividend": "N",
        "benchmark": "ดัชนี NASDAQ-100 Total Return ปรับด้วยต้นทุนการป้องกันความเสี่ยงอัตราแลกเปลี่ยน",
        "total_fee": 0.36,
        "min_sub": 1,
        "settlement": "T+2",
        "allocation": [("หน่วยลงทุนของกองทุนต่างประเทศ", 97.2), ("เงินฝากและตราสารตลาดเงิน", 2.4), ("สัญญาซื้อขายล่วงหน้า", 0.4)],
        "top5": [("Invesco QQQ Trust Series 1", 97.2), ("เงินฝากธนาคารไทยพาณิชย์", 1.6), ("พันธบัตรธนาคารแห่งประเทศไทย", 0.5), ("สัญญาฟอร์เวิร์ดเงินตราต่างประเทศ", 0.4), ("เงินฝากธนาคารกรุงเทพ", 0.3)],
        "policy_text": "<p>กองทุนลงทุนในหน่วยลงทุนของกองทุนรวมต่างประเทศเพียงกองทุนเดียว (Feeder Fund) คือ Invesco QQQ Trust Series 1 ซึ่งมีนโยบายสร้างผลตอบแทนให้ใกล้เคียงกับดัชนี NASDAQ-100 โดยเฉลี่ยในรอบปีบัญชีไม่น้อยกว่า 80% ของ NAV</p>",
    },
    {
        "proj_id": "M0654_2563",
        "target_total": 0.112,
        "code": "K-ATECH",
        "name_th": "กองทุนเปิดเค เอเชียน เทคโนโลยี หุ้นทุน",
        "name_en": "K Asian Technology Equity Fund",
        "amc_th": "บริษัทหลักทรัพย์จัดการกองทุน กสิกรไทย จำกัด",
        "amc_en": "KASIKORN ASSET MANAGEMENT COMPANY LIMITED",
        "unique_id": "C0000000021",
        "policy": "ตราสารทุน",
        "classes": ["K-ATECH-A(A)", "K-ATECH-A(D)", "K-ATECH-SSF"],
        "risk": "RS7",
        "risk_desc": "ลงทุนกระจุกตัวในหมวดอุตสาหกรรมเทคโนโลยี",
        "regis_date": "2020-11-24",
        "drift": 0.07,
        "vol": 0.21,
        "nav0": 10.0,
        "net_asset": 3_142_000_000,
        "feeder": "",
        "feeder_country": "",
        "fx": "ป้องกันความเสี่ยงจากอัตราแลกเปลี่ยนตามดุลยพินิจผู้จัดการกองทุน",
        "dividend": "N",
        "benchmark": "MSCI AC Asia ex Japan Information Technology Index (Net) ในสกุลเงินบาท",
        "total_fee": 1.91,
        "min_sub": 500,
        "settlement": "T+4",
        "allocation": [("หน่วยลงทุนต่างประเทศ", 58.4), ("หุ้นสามัญต่างประเทศ", 37.1), ("เงินฝากและตราสารตลาดเงิน", 4.5)],
        "top5": [("Taiwan Semiconductor Manufacturing", 9.8), ("Samsung Electronics", 7.2), ("Tencent Holdings", 6.4), ("SK Hynix", 5.1), ("Alibaba Group", 4.3)],
        "policy_text": "<p>กองทุนเน้นลงทุนในหุ้นของบริษัทในภูมิภาคเอเชียที่ดำเนินธุรกิจเกี่ยวข้องกับเทคโนโลยี โดยเฉลี่ยในรอบปีบัญชีไม่น้อยกว่า 80% ของ NAV</p>",
    },
    {
        "proj_id": "M0128_2559",
        "target_total": 0.415,
        "code": "SCBSET50",
        "name_th": "กองทุนเปิดไทยพาณิชย์ SET50 INDEX",
        "name_en": "SCB SET50 Index Fund",
        "amc_th": "บริษัทหลักทรัพย์จัดการกองทุน ไทยพาณิชย์ จำกัด",
        "amc_en": "SCB ASSET MANAGEMENT COMPANY LIMITED",
        "unique_id": "C0000000031",
        "policy": "ตราสารทุน",
        "classes": ["SCBSET50(A)", "SCBSET50(P)", "SCBSET50(SSF)"],
        "risk": "RS6",
        "risk_desc": "ลงทุนในตราสารทุนในประเทศเป็นหลัก",
        "regis_date": "2016-03-15",
        "drift": 0.03,
        "vol": 0.155,
        "nav0": 20.0,
        "net_asset": 12_480_000_000,
        "feeder": "",
        "feeder_country": "",
        "fx": "",
        "dividend": "N",
        "benchmark": "ดัชนีผลตอบแทนรวม SET50 (SET50 TRI)",
        "total_fee": 0.36,
        "min_sub": 1,
        "settlement": "T+2",
        "allocation": [("หุ้นสามัญ", 98.6), ("เงินฝากและตราสารตลาดเงิน", 1.4)],
        "top5": [("บมจ.เดลต้า อีเลคโทรนิคส์", 10.2), ("บมจ.ปตท.", 7.9), ("บมจ.ท่าอากาศยานไทย", 6.1), ("บมจ.ซีพี ออลล์", 5.4), ("บมจ.แอดวานซ์ อินโฟร์ เซอร์วิส", 5.0)],
        "policy_text": "<p>กองทุนมุ่งสร้างผลตอบแทนให้ใกล้เคียงกับดัชนี SET50 ให้มากที่สุด (Passive Management)</p>",
    },
    {
        "proj_id": "M0223_2553",
        "target_total": 0.462,
        "code": "K-FIXED",
        "name_th": "กองทุนเปิดเค ตราสารหนี้",
        "name_en": "K Fixed Income Fund",
        "amc_th": "บริษัทหลักทรัพย์จัดการกองทุน กสิกรไทย จำกัด",
        "amc_en": "KASIKORN ASSET MANAGEMENT COMPANY LIMITED",
        "unique_id": "C0000000021",
        "policy": "ตราสารหนี้",
        "classes": ["K-FIXED-A", "K-FIXED-SSF"],
        "risk": "RS4",
        "risk_desc": "ลงทุนในตราสารหนี้ทั่วไป",
        "regis_date": "2010-06-30",
        "drift": 0.021,
        "vol": 0.017,
        "nav0": 10.0,
        "net_asset": 41_260_000_000,
        "feeder": "",
        "feeder_country": "",
        "fx": "ป้องกันความเสี่ยงจากอัตราแลกเปลี่ยนทั้งจำนวน",
        "dividend": "N",
        "benchmark": "ThaiBMA Government Bond Index (1-3 ปี) 60% + ดัชนีตราสารหนี้ภาคเอกชน 40%",
        "total_fee": 0.53,
        "min_sub": 500,
        "settlement": "T+1",
        "allocation": [("พันธบัตรรัฐบาล", 46.3), ("หุ้นกู้เอกชน", 38.9), ("เงินฝาก", 14.8)],
        "top5": [("พันธบัตรรัฐบาล LB286A", 8.1), ("พันธบัตร ธปท.", 6.7), ("หุ้นกู้ บมจ.ปตท.", 4.2), ("หุ้นกู้ บมจ.ซีพี ออลล์", 3.8), ("เงินฝากธนาคารกสิกรไทย", 3.1)],
        "policy_text": "<p>กองทุนลงทุนในตราสารหนี้ภาครัฐและภาคเอกชนที่มีอันดับความน่าเชื่อถืออยู่ในระดับที่ลงทุนได้</p>",
    },
    {
        "proj_id": "M0480_2562",
        "target_total": 1.084,
        "code": "KFGBRAND-A",
        "name_th": "กองทุนเปิดกรุงศรีโกลบอลแบรนด์อิควิตี้-สะสมมูลค่า",
        "name_en": "Krungsri Global Brands Equity Fund-A",
        "amc_th": "บริษัทหลักทรัพย์จัดการกองทุน กรุงศรี จำกัด",
        "amc_en": "KRUNGSRI ASSET MANAGEMENT COMPANY LIMITED",
        "unique_id": "C0000000027",
        "policy": "ตราสารทุน",
        "classes": ["KFGBRAND-A", "KFGBRAND-D", "KFGBRAND-SSF"],
        "risk": "RS6",
        "risk_desc": "ลงทุนในตราสารทุนต่างประเทศเป็นหลัก",
        "regis_date": "2019-02-19",
        "drift": 0.12,
        "vol": 0.145,
        "nav0": 10.0,
        "net_asset": 22_915_000_000,
        "feeder": "Morgan Stanley Investment Funds - Global Brands Fund",
        "feeder_country": "Luxembourg",
        "fx": "ป้องกันความเสี่ยงจากอัตราแลกเปลี่ยนไม่น้อยกว่า 90%",
        "dividend": "N",
        "benchmark": "MSCI World Net Total Return USD Index ในสกุลเงินบาท",
        "total_fee": 1.61,
        "min_sub": 500,
        "settlement": "T+4",
        "allocation": [("หน่วยลงทุนของกองทุนต่างประเทศ", 96.8), ("เงินฝากและตราสารตลาดเงิน", 3.2)],
        "top5": [("MS Global Brands Fund", 96.8), ("เงินฝากธนาคารกรุงศรีอยุธยา", 1.9), ("พันธบัตร ธปท.", 0.7), ("สัญญาฟอร์เวิร์ด", 0.4), ("เงินฝากธนาคารกรุงเทพ", 0.2)],
        "policy_text": "<p>กองทุนลงทุนในหน่วยลงทุนของกองทุนรวมต่างประเทศเพียงกองเดียว ซึ่งลงทุนในหุ้นของบริษัทที่มีแบรนด์แข็งแกร่งทั่วโลก</p>",
    },
    {
        "proj_id": "M0092_2555",
        "target_total": 1.35,
        "code": "TMBGOLDS",
        "name_th": "กองทุนเปิดทหารไทย โกลด์ สิงคโปร์",
        "name_en": "TMB Gold Singapore Fund",
        "amc_th": "บริษัทหลักทรัพย์จัดการกองทุน อีสท์สปริง (ประเทศไทย) จำกัด",
        "amc_en": "EASTSPRING ASSET MANAGEMENT (THAILAND) CO.,LTD.",
        "unique_id": "C0000000045",
        "policy": "กองทุนรวมทางเลือก",
        "classes": ["main"],
        "risk": "RS8",
        "risk_desc": "ลงทุนในสินทรัพย์ทางเลือก (ทองคำ)",
        "regis_date": "2012-04-05",
        "drift": 0.085,
        "vol": 0.135,
        "nav0": 10.0,
        "net_asset": 2_640_000_000,
        "feeder": "SPDR Gold Trust",
        "feeder_country": "Singapore",
        "fx": "ไม่ป้องกันความเสี่ยงจากอัตราแลกเปลี่ยน",
        "dividend": "Y",
        "benchmark": "ราคาทองคำ London Gold PM Fix ในสกุลเงินบาท",
        "total_fee": 0.85,
        "min_sub": 1000,
        "settlement": "T+4",
        "allocation": [("หน่วยลงทุนต่างประเทศ (SPDR Gold Trust)", 98.1), ("เงินฝาก", 1.9)],
        "top5": [("SPDR Gold Trust", 98.1), ("เงินฝากธนาคารกรุงเทพ", 1.2), ("เงินฝากธนาคารกสิกรไทย", 0.7)],
        "policy_text": "<p>กองทุนลงทุนในหน่วยลงทุนของ SPDR Gold Trust เพื่อให้ผลตอบแทนใกล้เคียงกับราคาทองคำแท่ง</p>",
    },
]

FEE_ROWS = [
    ("ค่าธรรมเนียมการจัดการ (Management Fee)", 0.6),
    ("ค่าธรรมเนียมผู้ดูแลผลประโยชน์ (Trustee Fee)", 0.1),
    ("ค่าธรรมเนียมนายทะเบียนหน่วยลงทุน (Registrar Fee)", 0.2),
]


def stable_seed(*parts: str) -> int:
    """seed ที่ไม่เปลี่ยนตามรอบการรัน (hash() ของ Python สุ่ม salt ใหม่ทุกครั้งที่เปิดโปรเซส)"""
    digest = hashlib.md5("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def _nav_series(fund: dict, class_name: str, end: date) -> list[tuple[str, float]]:
    """สุ่มอนุกรม NAV รายวันทำการแบบ geometric brownian motion (seed คงที่ = ผลเหมือนเดิมทุกครั้ง)"""
    seed = stable_seed(fund["proj_id"], class_name)
    rng = random.Random(seed)
    start = date.fromisoformat(fund["regis_date"])
    # class ที่จ่ายปันผล/มีค่าธรรมเนียมต่างกันเล็กน้อย -> ผลตอบแทนต่างกันนิดหน่อย
    tweak = (seed % 7 - 3) * 0.004
    mu = fund["drift"] + tweak
    sigma = fund["vol"]
    dt = 1 / 252
    shock_day = start + timedelta(days=380)

    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    if not days:
        return []

    steps = []
    for day in days:
        drift = (mu - 0.5 * sigma**2) * dt
        # ใส่ช่วงตลาดหมี 1 ช่วงให้กราฟดูสมจริง (มี drawdown ให้เห็น)
        if shock_day <= day <= shock_day + timedelta(days=260):
            drift -= 0.0012
        steps.append(drift + sigma * (dt**0.5) * rng.gauss(0, 1))

    # บังคับให้ผลตอบแทนสะสมลงเอยตามเป้าหมาย (บวก tweak รายชนิดหน่วย) โดยยังคงรูปทรงกราฟเดิม
    import math

    target_log = math.log(1 + fund["target_total"] + tweak * 8)
    adjust = (target_log - sum(steps)) / len(steps)

    nav = fund["nav0"]
    out: list[tuple[str, float]] = []
    for day, step in zip(days, steps):
        nav *= math.exp(step + adjust)
        out.append((day.isoformat(), round(nav, 4)))
    return out


class DemoClient:
    """มี interface เหมือน SecClient แต่ตอบด้วยข้อมูลจำลอง"""

    demo = True

    def __init__(self, today: date | None = None):
        self.today = today or date.today()
        self._nav_cache: dict[tuple[str, str], list[tuple[str, float]]] = {}

    # ---------- helper ----------
    def _fund(self, proj_id: str) -> dict | None:
        return next((f for f in DEMO_FUNDS if f["proj_id"] == proj_id), None)

    def _nav(self, fund: dict, class_name: str) -> list[tuple[str, float]]:
        key = (fund["proj_id"], class_name)
        if key not in self._nav_cache:
            self._nav_cache[key] = _nav_series(fund, class_name, self.today)
        return self._nav_cache[key]

    def _match(self, needle: str) -> list[dict]:
        needle = (needle or "").strip().upper()
        if not needle:
            return list(DEMO_FUNDS)
        out = []
        for fund in DEMO_FUNDS:
            haystack = " ".join(
                [fund["proj_id"], fund["code"], fund["name_th"], fund["name_en"], fund["amc_th"]] + fund["classes"]
            ).upper()
            if needle in haystack:
                out.append(fund)
        return out

    # ---------- interface ----------
    def get(self, path: str, params: dict | None = None, ttl: int | None = None) -> dict:
        return {"message": "success", "items": self.fetch_all(path, params), "next_cursor": ""}

    def iter_items(self, path: str, params: dict | None = None, **kwargs):
        yield from self.fetch_all(path, params)

    def fetch_all(self, path: str, params: dict | None = None, **kwargs) -> list[dict]:
        params = dict(params or {})
        proj_id = params.get("proj_id")
        class_filter = params.get("fund_class_name")
        funds = [self._fund(proj_id)] if proj_id else self._match(params.get("project_info", ""))
        funds = [f for f in funds if f]

        if path.endswith("/general-info/profiles"):
            rows = []
            for fund in funds:
                for class_name in fund["classes"]:
                    if class_filter and class_filter != class_name:
                        continue
                    rows.append(
                        {
                            "unique_id": fund["unique_id"],
                            "comp_name_th": fund["amc_th"],
                            "comp_name_en": fund["amc_en"],
                            "proj_id": fund["proj_id"],
                            "proj_name_th": fund["name_th"],
                            "proj_name_en": fund["name_en"],
                            "proj_abbr_name": fund["code"],
                            "fund_status": "Registered",
                            "regis_date": fund["regis_date"],
                            "init_date": fund["regis_date"],
                            "policy_desc": fund["policy"],
                            "investment_policy_desc": fund["policy_text"],
                            "management_style": "PM" if "Index" in fund["name_en"] else "AM",
                            "proj_retail_type": "R",
                            "proj_term_flag": "N",
                            "feederfund_master_fund": fund["feeder"],
                            "feederfund_country": fund["feeder_country"],
                            "exchange_rate_protection_policy": fund["fx"],
                            "fund_class_name": class_name,
                            "fund_class_detail": "ชนิดสะสมมูลค่า" if class_name.endswith(("(A)", "-A", "A(A)")) else "ชนิดทั่วไป",
                            "fund_class_description": "สำหรับผู้ลงทุนทั่วไป",
                            "fund_class_tax_incentive_type": "SSF" if "SSF" in class_name else "",
                            "fund_class_isin_code": f"TH{stable_seed(class_name) % 10**10:010d}",
                        }
                    )
            return rows

        if path.endswith("/daily-info/nav"):
            start = params.get("start_nav_date") or "1900-01-01"
            end = params.get("end_nav_date") or "2999-12-31"
            rows = []
            for fund in funds:
                for class_name in fund["classes"]:
                    if class_filter and class_filter != class_name:
                        continue
                    series = self._nav(fund, class_name)
                    scale = fund["net_asset"] / (series[-1][1] if series else 1)
                    for nav_date, nav in series:
                        if start <= nav_date <= end:
                            rows.append(
                                {
                                    "proj_id": fund["proj_id"],
                                    "unique_id": fund["unique_id"],
                                    "fund_class_name": class_name,
                                    "nav_date": nav_date,
                                    "net_asset": round(nav * scale, 2),
                                    "last_val": nav,
                                    "sell_price": round(nav * 1.0005, 4),
                                    "buy_price": round(nav * 0.9995, 4),
                                    "sell_swap_price": nav,
                                    "buy_swap_price": nav,
                                }
                            )
            return rows

        if path.endswith("/factsheet/risk-spectrum"):
            return [
                {"proj_id": f["proj_id"], "risk_spectrum": f["risk"], "risk_spectrum_desc": f["risk_desc"], "end_date": self.today.isoformat()}
                for f in funds
            ]

        if path.endswith("/factsheet/benchmarks"):
            return [
                {"proj_id": f["proj_id"], "benchmark": f["benchmark"], "benchmark_remark": "", "end_date": self.today.isoformat()}
                for f in funds
            ]

        if path.endswith("/factsheet/statistics"):
            rows = []
            for fund in funds:
                series = self._nav(fund, class_filter or fund["classes"][0])
                rng = random.Random(fund["proj_id"])
                rows.append(
                    {
                        "proj_id": fund["proj_id"],
                        "fund_class_name": class_filter or fund["classes"][0],
                        "end_date": self.today.isoformat(),
                        "portfolio_turnover_ratio": f"{rng.uniform(0.2, 1.8):.2f}",
                        "recovering_period": "1 ปี 1 เดือน",
                        "portfolio_duration_period": "-" if fund["policy"] != "ตราสารหนี้" else "1 ปี 4 เดือน",
                        "maximum_drawdown": f"{-rng.uniform(8, 38):.2f}",
                        "sharpe_ratio": f"{rng.uniform(-0.2, 1.4):.2f}",
                        "beta": f"{rng.uniform(0.8, 1.1):.2f}",
                        "alpha": f"{rng.uniform(-3, 3):.2f}",
                        "tracking_error": f"{rng.uniform(0.5, 6):.2f}",
                        "fx_hedging": "98.50" if fund["fx"] else "0",
                        "yield_to_maturity": "-",
                    }
                )
            return rows

        if path.endswith("/factsheet/performance"):
            rows = []
            for fund in funds:
                class_name = class_filter or fund["classes"][0]
                series = self._nav(fund, class_name)
                import metrics as _m

                clean = _m.clean_series(series)
                mapping = {"3 months": "3M", "6 months": "6M", "1 year": "1Y", "3 years": "3Y", "5 years": "5Y", "since inception": "MAX"}
                days = dict(_m.PERIODS)
                rng = random.Random(fund["code"])
                for label, period_key in mapping.items():
                    result = _m.period_return(clean, period_key, days.get(period_key))
                    if not result.get("available"):
                        continue
                    value = result["annualized"] if result.get("annualized") is not None else result["return"]
                    for kind, val in (
                        ("ผลการดำเนินงานของกองทุนรวม", value * 100),
                        ("ผลการดำเนินงานของดัชนีชี้วัด", value * 100 + rng.uniform(-3, 3)),
                        ("ความผันผวนของกองทุนรวม", fund["vol"] * 100 + rng.uniform(-2, 2)),
                        ("ความผันผวนของดัชนีชี้วัด", fund["vol"] * 100 + rng.uniform(-2, 2)),
                    ):
                        rows.append(
                            {
                                "proj_id": fund["proj_id"],
                                "fund_class_name": class_name,
                                "end_date": self.today.isoformat(),
                                "performance_type_desc": kind,
                                "reference_period": label,
                                "performance_value": f"{val:.2f}",
                            }
                        )
            return rows

        if path.endswith("/factsheet/asset-allocation"):
            return [
                {"proj_id": f["proj_id"], "asset_seq": i + 1, "asset_name": name, "asset_ratio": ratio, "end_date": self.today.isoformat()}
                for f in funds
                for i, (name, ratio) in enumerate(f["allocation"])
            ]

        if path.endswith("/factsheet/top5-holdings"):
            return [
                {"proj_id": f["proj_id"], "asset_seq": i + 1, "asset_name": name, "asset_ratio": ratio, "end_date": self.today.isoformat()}
                for f in funds
                for i, (name, ratio) in enumerate(f["top5"])
            ]

        if path.endswith("/factsheet/dividend-policy"):
            return [
                {"proj_id": f["proj_id"], "fund_class_name": class_filter or "main", "dividend_policy": f["dividend"], "end_date": self.today.isoformat()}
                for f in funds
            ]

        if path.endswith("/factsheet/fees"):
            rows = []
            for fund in funds:
                rows.append(
                    {
                        "proj_id": fund["proj_id"],
                        "fund_class_name": class_filter or "main",
                        "end_date": self.today.isoformat(),
                        "fee_type_desc": "รวมค่าใช้จ่ายทั้งหมด",
                        "rate": fund["total_fee"],
                        "actual_value": fund["total_fee"],
                        "fee_other_desc": "ค่าธรรมเนียมรวมภาษีมูลค่าเพิ่มแล้ว",
                    }
                )
                rows.append(
                    {
                        "proj_id": fund["proj_id"],
                        "fund_class_name": class_filter or "main",
                        "end_date": self.today.isoformat(),
                        "fee_type_desc": "ค่าธรรมเนียมการขายหน่วยลงทุน (Front-end Fee)",
                        "rate": 1.0,
                        "actual_value": 0.0,
                        "fee_other_desc": "ปัจจุบันยกเว้นการเรียกเก็บ",
                    }
                )
            return rows

        if path.endswith("/general-info/mutual-fund-fees"):
            return [
                {
                    "proj_id": f["proj_id"],
                    "fund_class_name": f["classes"][0],
                    "fee_type_desc": name,
                    "rate": round(f["total_fee"] * share, 4),
                    "rate_unit": "ต่อปี ของมูลค่าทรัพย์สินสุทธิของกองทุนรวม",
                    "fee_other_desc": "",
                }
                for f in funds
                for name, share in FEE_ROWS
            ]

        if path.endswith("/factsheet/subscription-redemption-minimums"):
            return [
                {
                    "proj_id": f["proj_id"],
                    "fund_class_name": class_filter or "main",
                    "minimum_sub_ipo": f["min_sub"],
                    "minimum_sub": f["min_sub"],
                    "minimum_sub_cur": "THB",
                    "minimum_redempt": 0,
                    "lowbal_val": 0,
                    "end_date": self.today.isoformat(),
                }
                for f in funds
            ]

        if path.endswith("/factsheet/subscription-redemption-periods"):
            rows = []
            for fund in funds:
                rows.append({"proj_id": fund["proj_id"], "type": "subscription", "period": "ทุกวันทำการ", "settlement_period": "", "end_date": self.today.isoformat()})
                rows.append({"proj_id": fund["proj_id"], "type": "redemption", "period": "ทุกวันทำการ", "settlement_period": fund["settlement"], "end_date": self.today.isoformat()})
            return rows

        if path.endswith("/general-info/specifications"):
            return [
                {"proj_id": f["proj_id"], "spec_code": "FIF" if f["feeder"] else "LTF", "spec_desc": "กองทุนรวมที่ลงทุนในต่างประเทศ (FIF)" if f["feeder"] else "กองทุนรวมทั่วไป"}
                for f in funds
            ]

        if path.endswith("/factsheet/urls"):
            return [
                {
                    "proj_id": f["proj_id"],
                    "fund_class_name": f["classes"][0],
                    "amc_url_factsheet": "https://secopendata.sec.or.th/",
                    "pdf_factsheet": f"https://secdocumentstorage.blob.core.windows.net/fundfactsheet/{f['proj_id']}.pdf",
                    "as_of_date": self.today.isoformat(),
                }
                for f in funds
            ]

        if path.endswith("/daily-info/dividend-history"):
            rows = []
            for fund in funds:
                if fund["dividend"] != "Y":
                    continue
                for i in range(6):
                    day = self.today - timedelta(days=180 * (i + 1))
                    rows.append(
                        {
                            "proj_id": fund["proj_id"],
                            "class_abbr_name": fund["classes"][0],
                            "book_close_date": (day - timedelta(days=7)).isoformat(),
                            "dividend_date": day.isoformat(),
                            "dividend_value": round(0.25 + 0.05 * ((i * 7) % 5), 4),
                        }
                    )
            return rows

        if path.endswith("/general-info/amcs"):
            seen = {}
            for f in DEMO_FUNDS:
                seen[f["unique_id"]] = {"unique_id": f["unique_id"], "comp_name_th": f["amc_th"], "comp_name_en": f["amc_en"]}
            return list(seen.values())

        return []
