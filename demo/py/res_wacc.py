#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WACC 外部数据联网同步。

数据源（直连失败时依次走公共代理，与网页版 / 投资部工具同一链路）：
  ① FRED DGS10 —— 美元 10 年期国债收益率（每日）
  ② Damodaran ctryprem.html —— 全部国别评级 / 违约利差 / CRP / 总 ERP / 企业税率
  ③ Damodaran BetasGlobal.html —— 全部行业无杠杆 β

快照写入 ~/Library/Application Support/RNE 财务分析模型/wacc_live.json，
下次启动先读快照、再后台刷新；离线时沿用快照，无快照则用 res_wacc_data 内置基准。
"""
import os
import re
import ssl
import sys
import json
import html
import datetime
import urllib.request
import urllib.parse

import res_wacc_data as D

if sys.platform.startswith("win"):
    APP_DIR = os.path.join(
        os.environ.get("APPDATA") or os.path.expanduser("~"),
        "RNE 财务分析模型")
elif sys.platform == "darwin":
    APP_DIR = os.path.expanduser("~/Library/Application Support/RNE 财务分析模型")
else:
    APP_DIR = os.path.join(
        os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
        "RNE 财务分析模型")
CACHE = os.path.join(APP_DIR, "wacc_live.json")

URL_FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"
URL_CTRY = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html"
URL_BETA = "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/BetasGlobal.html"


def _ensure_dir():
    try:
        os.makedirs(APP_DIR, exist_ok=True)
    except Exception:
        pass


def _fetch(url, timeout=12):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    tries = [url,
             "https://api.allorigins.win/raw?url=" + urllib.parse.quote(url, safe=""),
             "https://corsproxy.io/?" + urllib.parse.quote(url, safe=""),
             "https://r.jina.ai/" + url]
    for u in tries:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "curl/8.0"})
            txt = urllib.request.urlopen(req, timeout=timeout, context=ctx).read()
            txt = txt.decode("latin-1", "replace")
            if txt and len(txt) > 500:
                return txt, u
        except Exception:
            continue
    return None, None


def _cells(row):
    return [re.sub(r"\s+", " ",
                   html.unescape(re.sub(r"<[^>]+>", "", x).replace("&nbsp;", " "))).strip()
            for x in re.findall(r"<td[^>]*>[\s\S]*?</td>", row, re.I)]


def _num(s):
    try:
        return float(str(s).replace("%", "").replace(",", "").strip())
    except Exception:
        return None


def parse_fred(text):
    lines = [l for l in (text or "").strip().splitlines() if "," in l]
    if len(lines) < 2:
        return None, None
    for line in reversed(lines[1:]):
        d, v = line.split(",")[0], line.split(",")[1]
        try:
            return float(v) / 100.0, d
        except Exception:
            continue
    return None, None


def parse_ctryprem(txt):
    out = {}
    for r in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", txt or "", re.I):
        c = _cells(r)
        if len(c) < 6 or not re.match(r"^[A-Za-z]{1,4}\d?$", c[1]):
            continue
        ds, crp, terp, tax = _num(c[2]), _num(c[3]), _num(c[4]), _num(c[5])
        if ds is None or crp is None:
            continue
        nm = re.sub(r"\s+", " ", re.sub(r"\s*\(updated.*\)", "", c[0], flags=re.I)).strip()
        out[nm] = {"rating": c[1], "ds": ds, "crp": crp,
                   "terp": terp, "tax": tax}
    return out


def parse_betas(txt):
    out = {}
    for r in re.findall(r"<tr[^>]*>[\s\S]*?</tr>", txt or "", re.I):
        c = _cells(r)
        if len(c) < 6:
            continue
        try:
            int(float(c[1]))
            bu = float(c[5])
        except Exception:
            continue
        nm = re.sub(r"\s+", " ", c[0]).strip()
        if len(nm) >= 2:
            out[nm] = bu
    return out


def _pct_to_dec_countries(raw):
    """Damodaran 表以百分数给出；转成小数供引擎/前端统一使用。"""
    return {k: {"rating": v.get("rating", ""),
                "ds": (v.get("ds") or 0.0) / 100.0,
                "crp": (v.get("crp") or 0.0) / 100.0,
                "terp": (None if v.get("terp") is None else v["terp"] / 100.0),
                "tax": (None if v.get("tax") is None else v["tax"] / 100.0)}
            for k, v in raw.items()}


def _embedded_countries():
    return _pct_to_dec_countries(D.COUNTRY_DB)


def _embedded_payload():
    return {"countries": _embedded_countries(),
            "sectors": dict(D.SECTOR_BU),
            "rf_usd": D.RF_DB["usd10y"] / 100.0,
            "rf_cny": D.RF_DB["rmb10y"] / 100.0,
            "asof": D.RF_DB.get("asof", "")}


def _read_cache():
    try:
        with open(CACHE, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict) or "countries" not in d or "sectors" not in d:
            return None
        return d
    except Exception:
        return None


def _write_cache(d):
    _ensure_dir()
    try:
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


def _payload(source, live, snap, error=None):
    countries = dict(_embedded_countries())
    countries.update(snap.get("countries") or {})
    sectors = dict(D.SECTOR_BU)
    sectors.update(snap.get("sectors") or {})
    return {
        "ok": True,
        "live": bool(live),
        "source": source,
        "rf_usd": snap.get("rf_usd", D.RF_DB["usd10y"] / 100.0),
        "rf_cny": snap.get("rf_cny", D.RF_DB["rmb10y"] / 100.0),
        "erp": D.MATURE_ERP / 100.0,
        "countries": countries,
        "sectors": sectors,
        "fetched_at": snap.get("fetched_at", ""),
        "asof": snap.get("asof", ""),
        "sources": {"rf": "FRED DGS10", "country": "Damodaran ctryprem",
                    "beta": "Damodaran BetasGlobal"},
        "error": error,
    }


def _fallback(error=None):
    return _payload("fallback", False, _embedded_payload(), error)


def fetch_live():
    """联网抓取；成功返回 payload（并写快照），失败返回 None。"""
    fr, _ = _fetch(URL_FRED)
    rf, asof = parse_fred(fr)
    ct, _ = _fetch(URL_CTRY)
    ctry = parse_ctryprem(ct)
    bt, _ = _fetch(URL_BETA)
    betas = parse_betas(bt)

    if rf is None or len(ctry) < 50 or len(betas) < 30:
        return None

    snap = {
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "asof": asof or datetime.date.today().isoformat(),
        "rf_usd": round(rf, 6),
        "rf_cny": D.RF_DB["rmb10y"] / 100.0,
        "countries": _pct_to_dec_countries(ctry),
        "sectors": betas,
    }
    _write_cache(snap)
    return _payload("live", True, snap)


def live_data(force=False):
    """force=True 时联网刷新；否则优先返回快照（无快照则内置基准）。"""
    if force:
        try:
            got = fetch_live()
            if got:
                return got
        except Exception as ex:
            err = f"{type(ex).__name__}: {ex}"
            cached = _read_cache()
            if cached:
                return _payload("cache", False, cached, f"联网失败：{err}")
            return _fallback(f"联网失败：{err}")
    cached = _read_cache()
    if cached:
        return _payload("cache", False, cached)
    return _fallback()


if __name__ == "__main__":
    import sys
    print(json.dumps(live_data(force="--live" in sys.argv), ensure_ascii=False, indent=2)[:2000])
