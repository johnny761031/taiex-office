#!/usr/bin/env python3
"""寫 stocks.json：上市個股（含 ETF）最新價、昨收、名稱，給「我的庫存」使用。
盤中：證交所 MIS 批次查詢（每批 100 檔）；非盤中：openapi STOCK_DAY_ALL。
價格只用交易所資料：MIS 當下無成交時沿用本日先前成交價，否則用最佳買賣報價中間價並標記 q=1。失敗則不覆寫。"""
import json, os, time, datetime, urllib.request
TZ = datetime.timezone(datetime.timedelta(hours=8)); UA = {"User-Agent": "Mozilla/5.0 (taiex-office updater)"}
def get(u, t=40): return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=t).read().decode("utf-8")
def f(x):
    try: return float(x)
    except Exception: return None
def universe():
    p = "universe.json"
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < 20 * 3600: return json.load(open(p, encoding="utf-8"))
    d = json.loads(get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"))
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False); return d
def from_day_all(d):
    s = {}; day = None
    for x in d:
        c, cl, ch = f(x.get("ClosingPrice")), x.get("Code"), f(x.get("Change"))
        if cl and cl is not None and c and ch is not None: s[x["Code"]] = [x["Name"], c, round(c - ch, 4), 0]
        day = x.get("Date") or day
    if day and len(day) == 7: day = f"{int(day[:3]) + 1911}-{day[3:5]}-{day[5:]}"
    return {"date": day, "time": "收盤", "mode": "收盤", "src": "證交所 STOCK_DAY_ALL", "s": s}
def from_mis(codes, now, old):
    prev = old.get("s", {}) if old.get("date") == now.strftime("%Y-%m-%d") else {}
    s, last = {}, ""
    for i in range(0, len(codes), 100):
        b = codes[i:i + 100]; u = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?json=1&delay=0&ex_ch=" + "|".join(f"tse_{c}.tw" for c in b)
        arr = None
        for k in range(3):
            try: arr = json.loads(get(u).strip())["msgArray"]; break
            except Exception: time.sleep(2)
        if arr is None: raise RuntimeError("MIS batch failed")
        for m in arr:
            if m.get("d") != now.strftime("%Y%m%d"): continue
            c, y, z = m.get("c"), f(m.get("y")), f(m.get("z"))
            if not c or not y: continue
            q = 0
            if z is None and c in prev and prev[c][3] == 0: z = prev[c][1]
            if z is None:
                bb, aa = f((m.get("b") or "").split("_")[0]), f((m.get("a") or "").split("_")[0])
                if bb and aa: z, q = round((bb + aa) / 2, 4), 1
                elif c in prev: z, q = prev[c][1], prev[c][3]
            if z is None: continue
            s[c] = [m.get("n", ""), z, y, q]; last = max(last, m.get("t", ""))
        time.sleep(.5)
    if len(s) < len(codes) * .5: raise RuntimeError(f"too few prices {len(s)}")
    return {"date": now.strftime("%Y-%m-%d"), "time": last, "mode": "盤中", "src": "證交所 MIS", "s": s}
def main():
    now = datetime.datetime.now(TZ); hm = now.hour * 100 + now.minute; t0 = time.time()
    try: old = json.load(open("stocks.json", encoding="utf-8"))
    except Exception: old = {}
    try:
        u = universe()
        if now.weekday() < 5 and 900 <= hm <= 1430:
            out = from_mis([x["Code"] for x in u], now, old)
            if hm > 1335: out["mode"] = "收盤"
        else: out = from_day_all(u)
    except Exception as e:
        print("stocks fetch failed, keep last good:", e); return
    if old.get("date") and out["date"] and out["date"] < old["date"]: print("older than current, skip"); return
    out["updatedAt"] = now.isoformat(timespec="seconds")
    json.dump(out, open("stocks.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"stocks {out['mode']} {out['date']} {out['time']} n={len(out['s'])} q={sum(v[3] for v in out['s'].values())} {time.time()-t0:.0f}s {os.path.getsize('stocks.json')//1024}KB")
if __name__ == "__main__": main()
