#!/usr/bin/env python3
"""GitHub Actions 用：盤中抓證交所 MIS 即時指數，收盤後抓 MI_INDEX，寫入 data.json。
抓取失敗時不覆寫（保留上一份成功資料）。只用標準函式庫。"""
import json, re, sys, datetime, urllib.request
TZ = datetime.timezone(datetime.timedelta(hours=8))
UA = {"User-Agent": "Mozilla/5.0 (taiex-office updater)"}
AGG = {"水泥窯製類指數","塑膠化工類指數","機電類指數","化學生技醫療類指數","電子工業類指數"}
MIS_CODES = ["t00"] + [f"t{i:02d}" for i in range(1, 32) if i not in (7, 13, 19)]
def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25).read().decode("utf-8")
def num(s): return float(str(s).replace(",", ""))
def mis(now):
    url = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp?json=1&delay=0&ex_ch=" + "|".join(f"tse_{c}.tw" for c in MIS_CODES)
    arr = json.loads(get(url).strip())["msgArray"]
    idx, secs, times, day = None, [], [], None
    for m in arr:
        if not m.get("n") or m.get("z") in (None, "-", "") or m.get("y") in (None, "-", ""): continue
        z, y = num(m["z"]), num(m["y"])
        it = {"name": m["n"], "close": z, "change": round(z - y, 2), "pct": round((z - y) / y * 100, 2)}
        day = m.get("d"); times.append(m.get("t", ""))
        if m["c"] == "t00": idx = it
        elif m["n"] not in AGG: it["short"] = m["n"].replace("類指數", ""); secs.append(it)
    if not idx or len(secs) < 20 or day != now.strftime("%Y%m%d"): return None
    secs.sort(key=lambda x: x["pct"], reverse=True)
    t = max(times)
    return {"source": "臺灣證券交易所 基本市況報導 (MIS) 即時指數", "title": "盤中即時（漲跌幅＝現值對昨收計算）",
            "date": f"{day[:4]}-{day[4:6]}-{day[6:]}", "dataTime": f"{day[:4]}-{day[4:6]}-{day[6:]} {t}", "mode": "盤中",
            "note": "盤中模式不含：綠能環保、數位雲端、運動休閒、居家生活（證交所即時 API 未提供）", "index": idx, "sectors": secs}
def close(now):
    day = now.date()
    for _ in range(10):
        j = json.loads(get(f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&type=IND&date={day:%Y%m%d}"))
        if j.get("stat") == "OK" and any(t.get("data") for t in j.get("tables", [])): break
        day -= datetime.timedelta(days=1)
    else: return None
    t = j["tables"][0]; idx, secs = None, []
    for r in t["data"]:
        name, neg = r[0], "-" in re.sub("<[^>]+>", "", r[2])
        it = {"name": name, "close": num(r[1]), "change": -num(r[3]) if neg else num(r[3]), "pct": num(r[4])}
        if name == "發行量加權股價指數": idx = it
        elif name.endswith("類指數") and name not in AGG: it["short"] = name[:-3]; secs.append(it)
    secs.sort(key=lambda x: x["pct"], reverse=True); d = j["date"]
    return {"source": "臺灣證券交易所 MI_INDEX", "title": t["title"], "date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
            "dataTime": f"{d[:4]}-{d[4:6]}-{d[6:]} 收盤", "mode": "收盤", "index": idx, "sectors": secs}
def main():
    now = datetime.datetime.now(TZ); out = None
    hm = now.hour * 100 + now.minute
    try:
        if now.weekday() < 5 and 900 <= hm <= 1345: out = mis(now)
        if out is None: out = close(now)
            # 收盤後 MI_INDEX 尚未發布當日資料時，若 MIS 有當日最終值則用 MIS
        if out and out["mode"] == "收盤" and now.weekday() < 5 and hm > 1330 and out["date"] != now.strftime("%Y-%m-%d"):
            m = mis(now)
            if m: m["mode"] = "收盤"; m["title"] = "今日收盤（MIS 即時值，正式收盤表尚未發布）"; m["dataTime"] = m["dataTime"]; out = m
    except Exception as e:
        print("fetch failed, keep last good data:", e); return
    if not out or not out.get("index"): print("no data, keep last good"); return
    out["isSample"] = False; out["fetchedAt"] = now.isoformat(timespec="seconds")
    try: old = json.load(open("data.json", encoding="utf-8"))
    except Exception: old = {}
    if {k: v for k, v in old.items() if k != "fetchedAt"} == {k: v for k, v in out.items() if k != "fetchedAt"}:
        print("unchanged"); return
    import os; json.dump(out, open("data.json.tmp", "w", encoding="utf-8"), ensure_ascii=False, indent=1); os.replace("data.json.tmp", "data.json")
    print("updated", out["mode"], out["dataTime"], out["index"])
if __name__ == "__main__": main()
