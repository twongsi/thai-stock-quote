"""ดึงข้อมูลชุดตัวอย่าง (presets) แล้วเขียนเป็น data.json สำหรับฝังในหน้า RRG Studio"""
import json, sys
from fetch_prices import table, fetch

PRESETS = [
  {"id":"us-sector","name":"US Sectors (SPDR)","bench":"SPY","tickers":{
    "XLK":"Technology","XLC":"Communication","XLY":"Cons. Discretionary","XLF":"Financials","XLI":"Industrials",
    "XLB":"Materials","XLE":"Energy","XLV":"Health Care","XLP":"Cons. Staples","XLU":"Utilities","XLRE":"Real Estate"}},
  {"id":"us-theme","name":"US Thematic ETFs","bench":"SPY","tickers":{
    "SMH":"Semiconductors","IGV":"Software","CIBR":"Cybersecurity","XBI":"Biotech","ITA":"Aerospace & Defense",
    "KRE":"Regional Banks","XHB":"Homebuilders","ICLN":"Clean Energy","URA":"Uranium","GDX":"Gold Miners",
    "ARKK":"Disruptive Innovation","PAVE":"Infrastructure"}},
  {"id":"country","name":"Country ETFs","bench":"ACWI","tickers":{
    "SPY":"United States","VGK":"Europe","EWJ":"Japan","FXI":"China large-cap","EWY":"South Korea","EWT":"Taiwan",
    "INDA":"India","EWZ":"Brazil","THD":"Thailand","VNM":"Vietnam","EIDO":"Indonesia","EWS":"Singapore"}},
  {"id":"us-mega","name":"US Mega-cap Stocks","bench":"QQQ","tickers":{
    "AAPL":"Apple","MSFT":"Microsoft","NVDA":"NVIDIA","AMZN":"Amazon","GOOGL":"Alphabet","META":"Meta",
    "TSLA":"Tesla","AVGO":"Broadcom","NFLX":"Netflix","AMD":"AMD","COST":"Costco","PLTR":"Palantir"}},
  {"id":"set-large","name":"Thai SET Large-caps","bench":"TDEX.BK","tickers":{
    "PTT.BK":"PTT","PTTEP.BK":"PTT Exploration","AOT.BK":"Airports of Thailand","CPALL.BK":"CP ALL",
    "ADVANC.BK":"Advanced Info Service","TRUE.BK":"True Corp","KBANK.BK":"Kasikornbank","SCB.BK":"SCB X",
    "BBL.BK":"Bangkok Bank","GULF.BK":"Gulf Development","BDMS.BK":"Bangkok Dusit Medical","DELTA.BK":"Delta Electronics",
    "CPN.BK":"Central Pattana","SCC.BK":"Siam Cement","CRC.BK":"Central Retail","MINT.BK":"Minor International"}},
]

# ---------- SET industry / sector proxies (equal-weight baskets) ----------
SET_SECTORS = {  # sector code: (ชื่อ, สมาชิกหลัก)
  "BANK":("Banking",["KBANK","SCB","BBL","KTB","TTB","KKP","TISCO"]),
  "FIN":("Finance & Securities",["KTC","MTC","SAWAD","TIDLOR","AEONTS"]),
  "INSUR":("Insurance",["BLA","TLI","TQM"]),
  "ENERG":("Energy & Utilities",["PTT","PTTEP","GULF","TOP","BCP","OR","BGRIM","EGCO","GPSC","RATCH","BANPU","EA"]),
  "PETRO":("Petrochemicals",["IVL","PTTGC","IRPC"]),
  "PROP":("Property Development",["CPN","LH","AP","SPALI","WHA","AMATA"]),
  "CONMAT":("Construction Materials",["SCC","TOA","DCC","TASCO"]),
  "CONS":("Construction Services",["CK","STECON"]),
  "COMM":("Commerce",["CPALL","CRC","HMPRO","BJC","CPAXT","GLOBAL"]),
  "HELTH":("Health Care Services",["BDMS","BH","BCH","CHG"]),
  "TOURISM":("Tourism & Leisure",["CENTEL","ERW"]),
  "TRANS":("Transportation",["AOT","BEM","BTS","BA"]),
  "MEDIA":("Media & Publishing",["VGI","PLANB"]),
  "ICT":("Information & Communication Tech.",["ADVANC","TRUE","JAS"]),
  "ETRON":("Electronic Components",["DELTA","KCE","HANA","CCET"]),
  "FOOD":("Food & Beverage",["CPF","TU","CBG","OSP","MINT","TFG","GFPT","BTG","M"]),
  "AUTO":("Automotive",["AH","SAT"]),
  "PKG":("Packaging",["SCGP"]),
  "FASHION":("Fashion & Home",["MC","SABINA","DDD","KAMART","TNL"]),
}
SET_INDUSTRIES = {
  "AGRO":("Agro & Food Industry",["FOOD"]),
  "CONSUMP":("Consumer Products",["FASHION"]),
  "FINCIAL":("Financials",["BANK","FIN","INSUR"]),
  "INDUS":("Industrials",["PETRO","AUTO","PKG"]),
  "PROPCON":("Property & Construction",["PROP","CONMAT","CONS"]),
  "RESOURC":("Resources",["ENERG"]),
  "SERVICE":("Services",["COMM","HELTH","TOURISM","TRANS","MEDIA"]),
  "TECH":("Technology",["ICT","ETRON"]),
}

def basket(member_series, dates):
    """ดัชนี equal-weight: rebalance ทุกงวด, ใช้ค่าเฉลี่ยผลตอบแทนของสมาชิกที่มีข้อมูล"""
    idx, out, prev = 100.0, [], None
    for d in dates:
        if prev is not None:
            rets = [s[d]/s[prev]-1 for s in member_series if d in s and prev in s]
            if rets: idx *= 1 + sum(rets)/len(rets)
        out.append(idx); prev = d
    return out

def ffill_on(series, dates):
    last, out = None, {}
    keys = sorted(series)
    j = 0
    for d in dates:
        while j < len(keys) and keys[j] <= d: last = series[keys[j]]; j += 1
        out[d] = last
    return out

def set_preset(pid, name, groups, expand):
    res = {}
    for interval, rng in (("1wk","5y"),("1d","2y")):
        bench, _ = fetch("TDEX.BK", interval, rng); dates = sorted(bench)
        cache = {}
        cols = [[bench[d] for d in dates]]
        for code,(label,members) in groups.items():
            stocks = expand(members)
            ser = []
            for s in stocks:
                if s not in cache:
                    try: cache[s] = fetch(s+".BK", interval, rng)[0]
                    except Exception: cache[s] = {}
                ser.append(cache[s])
            cols.append([float(f"{v:.6g}") for v in basket(ser, dates)])
        res["weekly" if interval=="1wk" else "daily"] = {"dates":dates,"cols":cols}
    names = {c: f"{l} · {len(expand(m))} ตัว" for c,(l,m) in groups.items()}
    return {"id":pid,"name":name,"bench":"TDEX.BK","symbols":list(groups),"names":names,
            "members":{c:expand(m) for c,(l,m) in groups.items()},**res}

# ---------- world indices in USD ----------
WORLD = [
  ("dev","World Indices · Developed (USD)",{
    "^GSPC":("S&P 500 · US","USD"),"^STOXX50E":("Euro STOXX 50 · Eurozone","EUR"),"^FTSE":("FTSE 100 · UK","GBP"),
    "^GDAXI":("DAX · Germany","EUR"),"^FCHI":("CAC 40 · France","EUR"),"^SSMI":("SMI · Switzerland","CHF"),
    "^N225":("Nikkei 225 · Japan","JPY"),"^AXJO":("ASX 200 · Australia","AUD"),"^GSPTSE":("TSX · Canada","CAD"),
    "^HSI":("Hang Seng · Hong Kong","HKD"),"^STI":("STI · Singapore","SGD"),"^TA125.TA":("TA-125 · Israel","ILS")}),
  ("em","World Indices · Emerging & ASEAN (USD)",{
    "000001.SS":("Shanghai Comp. · China","CNY"),"^KS11":("KOSPI · Korea","KRW"),"^TWII":("TAIEX · Taiwan","TWD"),
    "^NSEI":("Nifty 50 · India","INR"),"^BVSP":("Ibovespa · Brazil","BRL"),"^MXX":("IPC · Mexico","MXN"),
    "^J203.JO":("JSE All Share · South Africa","ZAR"),"^JKSE":("JCI · Indonesia","IDR"),"^KLSE":("KLCI · Malaysia","MYR"),
    "TDEX.BK":("SET50 (TDEX) · Thailand","THB"),"VNM":("VanEck Vietnam ETF · Vietnam","USD"),"EPHE":("iShares Philippines ETF · Philippines","USD")}),
]
SHORT = {"^GSPC":"US","^STOXX50E":"EURO","^FTSE":"UK","^GDAXI":"DE","^FCHI":"FR","^SSMI":"CH","^N225":"JP","^AXJO":"AU",
  "^GSPTSE":"CA","^HSI":"HK","^STI":"SG","^TA125.TA":"IL","000001.SS":"CN","^KS11":"KR","^TWII":"TW","^NSEI":"IN",
  "^BVSP":"BR","^MXX":"MX","^J203.JO":"ZA","^JKSE":"ID","^KLSE":"MY","TDEX.BK":"TH","VNM":"VN","EPHE":"PH"}

def world_preset(pid, name, members):
    ok = {}
    for sym, v in members.items():  # ตัวที่ดึงไม่ได้ (ราคาหรืออัตราแลกเปลี่ยน) ข้ามไป ไม่ให้ทั้งชุดล้ม
        try:
            fetch(sym, "1wk", "1mo")
            if v[1] != "USD": fetch(f"{v[1]}=X", "1wk", "1mo")
            ok[sym] = v
        except Exception as e:
            print("skip", sym, e, file=sys.stderr)
    members = ok
    res = {}
    for interval, rng in (("1wk","5y"),("1d","2y")):
        bench, _ = fetch("ACWI", interval, rng); dates = sorted(bench)
        cols = [[bench[d] for d in dates]]; fx = {}
        for sym,(label,ccy) in members.items():
            px = ffill_on(fetch(sym, interval, rng)[0], dates)
            if ccy != "USD":
                if ccy not in fx: fx[ccy] = ffill_on(fetch(f"{ccy}=X", interval, rng)[0], dates)
                f = fx[ccy]
                col = [None if px[d] is None or not f[d] else px[d]/f[d] for d in dates]  # local ÷ (local per USD)
            else: col = [px[d] for d in dates]
            cols.append([None if v is None else float(f"{v:.6g}") for v in col])
        res["weekly" if interval=="1wk" else "daily"] = {"dates":dates,"cols":cols}
    syms = [SHORT[s] for s in members]
    return {"id":pid,"name":name,"bench":"ACWI","symbols":syms,
            "names":{SHORT[s]:f"{l} ({s})" for s,(l,c) in members.items()},**res}

def pack(rows, n):
    dates=[d for d,_ in rows]
    cols=[[None if r[i] is None else float(f"{r[i]:.5g}") for _,r in rows] for i in range(n)]
    return {"dates":dates,"cols":cols}

out=[]
for p in PRESETS:
    syms=list(p["tickers"])
    w,mw=table(p["bench"],syms,"1wk","5y")
    ok=[s for s in syms if s not in mw["skipped"]]
    d,md=table(p["bench"],ok,"1d","2y")
    if md["skipped"]:  # ให้รายการตรงกันทั้งรายสัปดาห์และรายวัน
        ok=[s for s in ok if s not in md["skipped"]]
        w,_=table(p["bench"],ok,"1wk","5y"); d,_=table(p["bench"],ok,"1d","2y")
    out.append({"id":p["id"],"name":p["name"],"bench":p["bench"],"symbols":ok,
                "names":{s:p["tickers"][s] for s in ok},
                "weekly":pack(w,len(ok)+1),"daily":pack(d,len(ok)+1)})
    print(p["id"],len(ok),"syms",len(w),"wk",len(d),"d",w[-1][0],file=sys.stderr)
sec = lambda m: m
ind = lambda m: [x for sc in m for x in SET_SECTORS[sc][1]]
out.insert(4, set_preset("set-industry","SET Industry Groups (proxy)",SET_INDUSTRIES,ind))
out.insert(5, set_preset("set-sector","SET Sectors (proxy)",SET_SECTORS,sec))
for pid,name,mem in WORLD: out.append(world_preset("world-"+pid,name,mem))
for p in out[4:6]+out[-2:]: print(p["id"],len(p["symbols"]),len(p["weekly"]["dates"]),p["weekly"]["dates"][-1],file=sys.stderr)
json.dump({"asof":out[0]["daily"]["dates"][-1],"presets":out},open("data.json","w"),separators=(",",":"))
