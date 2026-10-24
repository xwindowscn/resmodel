#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RNE 项目财务分析模型 —— macOS 桌面版（WebView 界面）。

界面在 web/ 目录；计算全部由 res_engine.compute 完成。
"""
import json
import os
import sys
import time
import tempfile
import datetime

import numpy as np

import res_engine as E
import res_wacc
import res_wacc_data as WD
from res_schema import (GROUPS, CHOICES, TABLE_SPECS, SPECIAL_TABLES, CCY_CODES, CCY_MAP,
                        ALL_TABLE_NAMES, CARD_DEFS, CARD_UNITS,
                        FIELD_RULES, FIELD_DISABLE, FIELD_NOTES, FIELD_HINTS, NOTES_EN, en, en_list,
                        display_value, coerce_params, build_extra,
                        resolve_value, fmt_cell, fmt_num, fmt_pct,
                        build_decision, build_lcoe, build_wacc, build_glossary,
                        build_wacc_pack, build_wacc_compare, build_wacc_sens)
from res_export import export_workbook, SHEET_EN, LANGS, ALL_SHEETS
import res_license

APP_VERSION = "3.6.3"

# 左栏"算出来的"字段：不作为输入参数，随每次计算刷新（对应网页版的 .field.computed）
DERIVED_FIELDS = {
    # 电站部分（装机与发电组）：小时数 + 电站总投资引用
    "装机与发电": [
        ("d_stor_eq_hours", "储能等效小时数", "Storage Equivalent Hours", "h/年", None,
         "= 储能配置比例 × 年充放天数 × 储能时长", "= storage ratio × cycling days × duration"),
        ("d_guar_hours_y1", "首年保障收购小时数", "Guaranteed Hours (Year 1)", "h/年", None,
         "=（首年发电小时 − 市场化交易小时 − 储能等效小时 − 超发小时）×（1 − 线损率）",
         "= (first-year hours − market hours − storage equivalent hours − excess hours) × (1 − line loss)"),
        ("d_station_invest_ref1", "电站总投资（引用）", "Station Total Investment (ref.)", "万元", None,
         "随「电站 EPC 单价 / 管理费率」实时变化", "Updates live with station EPC price and fee rate"),
        ("d_storage_invest_ref1", "储能全寿命周期总投资（引用）", "Storage Lifetime Investment (ref.)", "万元", None,
         "随储能比例 / 时长 / EPC 单价变化", "Updates with storage ratio, duration and EPC price"),
        ("d_predev_ref1", "项目前期开发费（引用）", "Pre-development Cost (ref.)", "万元", None,
         "= 项目前期开发费单价 × 直流容量 × 100（含技术开发费）",
         "= pre-development unit price × DC capacity × 100 (incl. technical development fee)"),
        ("d_total_invest_ref1", "项目总投资（引用）", "Total Investment (ref.)", "万元", None,
         "= 电站总投资 + 储能总投资 + 前期开发费 + 建设期利息 + 流动资金",
         "= station + storage + pre-development + IDC + working capital"),
    ],
    # 储能部分：储能三项 + 电站/项目总投资引用
    "储能": [
        ("d_storage_tariff_ref", "储能上网电价（引用「电价」组）", "Storage Feed-in Tariff (ref.)", "元/kWh", None,
         "引用「电价」组同名参数；未填时等于保障收购电价",
         "Mirrors the parameter in Tariffs; equals the guaranteed tariff when left blank"),
        ("d_storage_epc", "储能 EPC 总价（初始投资）", "Storage EPC Price (initial investment)", "万元", "storage_unit_price",
         "= 交流容量 × 配置比例 × 储能时长 × 储能 EPC 单价（不含后续更换）",
         "= AC capacity × ratio × duration × storage EPC unit price (excl. replacements)"),
        ("d_storage_mgmt_fee", "储能业主管理费（EPC 之外另计）", "Storage Owner Mgmt Fee (on top of EPC)", "万元", "storage_unit_price",
         "= 储能 EPC 总价 × 储能建设管理费率", "= storage EPC × storage management fee rate"),
        ("d_storage_initial_invest", "储能初始总投资", "Storage Initial Total Investment", "万元", "storage_unit_price",
         "= 储能 EPC 总价 + 储能业主管理费", "= storage EPC + storage owner mgmt fee"),
        ("d_storage_invest", "储能全寿命周期总投资", "Storage Lifetime Total Investment", "万元", None,
         "= 储能初始总投资 + 各次更换电池投资按 WACC 折现到现在的现值",
         "= storage initial total investment + PV of future battery replacements at WACC"),
        ("d_storage_ratio_ref", "配置比例（在「基本情形」设置）", "Storage Ratio (set in General)", "", None,
         "在本组不可改；用于储能等效小时与租赁收入", "Set in General; drives storage equivalent hours and lease revenue"),
        ("d_storage_duration_ref", "配置时长（在「基本情形」设置）", "Storage Duration (set in General)", "", None,
         "在本组不可改；用于储能 EPC 与租赁收入", "Set in General; drives storage EPC and lease revenue"),
        ("d_station_invest_ref2", "电站总投资（引用）", "Station Total Investment (ref.)", "万元", None,
         "随「储能」参数调整时一并观察总投资变化", "Watch station investment while tuning storage parameters"),
        ("d_total_invest_ref2", "项目总投资（引用）", "Total Investment (ref.)", "万元", None,
         "= 电站总投资 + 储能总投资 + 建设期利息 + 流动资金", "= station + storage + IDC + working capital"),
        ("d_storage_per_wh", "储能每瓦时投资", "Storage Cost per Wh", "元/Wh", None,
         "= 储能总投资 ÷（交流容量 × 配置比例 × 储能时长 × 10⁶）",
         "= storage total investment ÷ (AC capacity × ratio × duration × 10⁶ Wh)"),
    ],
    # 电站投资组：电站自身三项 + 项目汇总
    "电站投资": [
        ("d_epc_station", "电站 EPC 总价", "Station EPC Price", "万元", "epc_price_station",
         "= 直流容量(MW) × 电站 EPC 单价(元/W) × 100",
         "= DC capacity (MW) × station EPC unit price (CNY/W) × 100"),
        ("d_station_mgmt_fee", "电站业主管理费（EPC 之外另计）", "Station Owner Mgmt Fee (on top of EPC)", "万元", "epc_price_station",
         "= 电站 EPC 总价 × 电站建设管理费率", "= station EPC × station management fee rate"),
        ("d_station_invest", "电站总投资", "Station Total Investment", "万元", "epc_price_station",
         "= 电站 EPC 总价 + 电站业主管理费", "= station EPC + station owner mgmt fee"),
        ("d_total_invest", "项目总投资", "Total Investment", "万元", None,
         "= 电站总投资 + 储能总投资 + 建设期利息 + 流动资金", "= station + storage + IDC + working capital"),
        ("d_capex_per_kw", "单位建设投资", "Unit Construction Cost", "元/Wp", None,
         "= 建设投资合计 ÷ 直流容量（元/Wp，派生，不可填）", "= construction investment ÷ DC capacity (CNY/Wp, derived)"),
    ],
    # 电价组
    "电价": [
        ("d_guar_tariff", "保障收购电价（实际上网电价）", "Guaranteed Tariff (actual grid price)", "元/kWh", "benchmark_tariff",
         "=（基准电价 PPA − 过网费 − 辅助服务费）×（1 − 保障电价折让）+ 差价补贴单价（仅在差价补贴年限内叠加，之后回落为不含补贴的实际上网电价）",
         "= (PPA − grid fee − ancillary fee) × (1 − guarantee discount) + subsidy price "
         "(added only within the subsidy years; afterwards reverts to the unsubsidised grid price)"),
    ],
}


def _is_money_unit(u):
    u = str(u or "")
    if not u:
        return False
    if "美元" in u or u.strip() == "元/美元":
        return False
    return u.startswith("万元") or u.startswith("元/")


def _ccy_unit(u, wan, usd=True, prefix="美元"):
    u = str(u or "")
    if not usd or not _is_money_unit(u):
        return u
    return wan if u.startswith("万元") else u.replace("元/", prefix + "/", 1)


def _ccy_unit_en(u, wan_en, usd=True, prefix="美元"):
    u = str(u or "")
    if not _is_money_unit(u):
        return en(u) if u else u
    if not usd:
        return en(u) if en(u) else u
    if u.startswith("万元"):
        return wan_en
    return en(u).replace("CNY/", "USD/", 1) if en(u) else u.replace("元/", "美元/", 1)


NON_MONEY_SRC = {
    "yr", "k", "hours", "h_plant", "h_storage",
    "gen", "gen_guar", "gen_mkt", "gen_over", "gen_plant", "gen_storage", "gen_lease",
    "dscr", "icr", "dep_rate", "amort_rate",
}


def build_derived(m, scale=1.0, munit="万元", munit_en="10K CNY"):
    """电站 / 储能各自的 EPC→总投资链，全部取引擎派生值（口径唯一）。"""
    p = m["p"]
    tot = float(p["total_investment"])
    dc = float(p["cap_dc_mw"])
    stor_eq = float(p["storage_ratio"] * p["storage_days"] * p["storage_duration"])
    _mwh = float(p["cap_ac_mw"]) * float(p["storage_ratio"]) * float(p["storage_duration"])
    _per_wh = (float(p["storage_invest"]) * 1e4 / (_mwh * 1e6)) if _mwh else 0.0
    guar_y1 = (float(p["op_hours_y1"]) - stor_eq
               - float(p.get("market_trade_hours") or 0.0)
               - float(p.get("overgen_hours") or 0.0)) \
              * (1.0 - float(p.get("line_loss") or 0.0))
    _disc = float(p.get("guarantee_discount") or 0.0)
    _net_tariff = (float(p["benchmark_tariff"]) - float(p.get("grid_fee") or 0.0)
                   - float(p.get("ancillary_fee") or 0.0))
    _guar_tariff = _net_tariff * (1.0 - _disc) + float(p.get("subsidy_price") or 0.0)
    def money(x):
        return f"{float(x) * scale:,.1f}"

    def price(x, nd=4):
        return f"{float(x) * scale:,.{nd}f}"

    return {
        "d_guar_tariff": price(_guar_tariff),
        "d_station_invest_ref1": money(p['station_invest']),
        "d_storage_invest_ref1": money(p['storage_invest']),
        "d_predev_ref1": money(p['predev']),
        "d_station_invest_ref2": money(p['station_invest']),
        "d_total_invest_ref1": money(p['total_investment']),
        "d_total_invest_ref2": money(p['total_investment']),
        "d_storage_tariff_ref": (price(float(p['storage_elec_price']))
                                 if float(p.get("storage_elec_price") or 0) > 0
                                 else price(_guar_tariff)),
        "d_storage_per_wh": price(_per_wh),
        "d_stor_eq_hours": f"{stor_eq:,.1f}",
        "d_guar_hours_y1": f"{guar_y1:,.1f}",
        "d_storage_ratio_ref": f"{float(p['storage_ratio']) * 100:,.0f}%",
        "d_storage_duration_ref": f"{float(p['storage_duration']):,.1f} h",
        "d_epc_station": f"{float(p['epce_station']):,.1f}",
        "d_station_mgmt_fee": money(p['station_mgmt_fee']),
        "d_station_invest": money(p['station_invest']),
        "d_storage_epc": money(p['storage_epc']),
        "d_storage_mgmt_fee": money(p['storage_mgmt_fee']),
        "d_storage_initial_invest": money(p['storage_initial_invest']),
        "d_storage_invest": money(p['storage_invest']),
        "d_total_invest": money(tot),
        "d_capex_per_kw": price(float(p['capex_per_kw']) / 1000),
    }


def asset_path(*parts):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def _build_stamp():
    try:
        with open(asset_path("web", "build_stamp.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def _app_name():
    """应用名 = 基础名 + 版本号，例如 RES Financial Model v3.2（general）。"""
    base = ""
    try:
        with open(asset_path("web", "app_name.txt"), encoding="utf-8") as f:
            base = f.read().strip()
    except OSError:
        pass
    if not base:
        base = "RES Financial Model（general）"
    tag = f"v{APP_VERSION}"
    if tag in base:
        return base
    # 把版本号插在括号限定符之前：RES Financial Model（general）→ RES Financial Model v3.2（general）
    for i, ch in enumerate(base):
        if ch == "（":
            return f"{base[:i].rstrip()} {tag}{base[i:]}"
    return f"{base} {tag}"


APP_NAME = _app_name()


def _license_enabled():
    try:
        with open(asset_path("web", "license_mode.txt"), encoding="utf-8") as f:
            return f.read().strip() == "on"
    except OSError:
        return False


def _num(x, nd=4):
    """numpy 标量 → JSON 安全数值。"""
    v = float(x)
    return None if not np.isfinite(v) else round(v, nd)


def _fmt_card(x, kind):
    if kind == "pct":
        return fmt_pct(x)
    if kind == "raw4":
        return fmt_num(x, 4)
    if kind == "num2":
        return fmt_num(x, 2)
    if kind == "num1":
        return fmt_num(x, 1)
    return fmt_num(x, 0)


class Api:
    def __init__(self, license_client=None):
        self.window = None
        self.last = None
        self.live = None
        self._current_path = None      # 当前命名的项目文件（保存时直接覆盖）
        self._fx = None                # USD/CNY 实时汇率缓存
        self._fx_ts = 0.0
        self._fx_src = ""
        self.license = license_client or res_license.Client(enabled=False)

    def _live(self):
        if self.live is None:
            self.live = res_wacc.live_data(force=False)
        return self.live

    # ── WACC 选择项 ───────────────────────────────────────────────────
    def _ccy_options(self, country=""):
        live = self._live()
        local = WD.local_ccy_of(country) if country else None
        rf_usd = float(live.get("rf_usd") or 0.0) * 100
        rf_cny = float(live.get("rf_cny") or 0.0) * 100
        opts = [
            {"v": "CNY", "t": f"人民币 RMB（10Y {rf_cny:.3f}%）",
             "t_en": f"Chinese Yuan（10Y {rf_cny:.3f}%）"},
            {"v": "USD", "t": f"美元 USD（10Y {rf_usd:.3f}%）",
             "t_en": f"US Dollar（10Y {rf_usd:.3f}%）"},
        ]
        if local:
            info = WD.LOCAL_CCY_DB.get(local) or {}
            rf = float(info.get("rf") or 0.0)
            opts.append({
                "v": "LOCAL",
                "t": f"本国货币 {info.get('cn', local)} {local}（10Y {rf:.3f}%）",
                "t_en": f"Local {info.get('en', local)} {local}（10Y {rf:.3f}%）",
            })
        return opts

    def _field_options(self, country=""):
        live = self._live()
        countries = live.get("countries") or {}
        sectors = live.get("sectors") or {}
        order = [c for c in WD.COUNTRY_PRIORITY if c in countries]
        order += sorted(c for c in countries if c not in order)
        return {
            "wacc_country": [{"v": c, "t": WD.country_label(c)} for c in order],
            "wacc_sector": [{"v": s, "t": f"{s}（βu {sectors[s]:.4f}）"}
                            for s in sorted(sectors)],
            "wacc_ccy": self._ccy_options(country),
            "rd_method": [
                {"v": "1", "t": "是（合成评级法）", "t_en": "Yes (synthetic rating)"},
                {"v": "0", "t": "否（投资人指定）", "t_en": "No (investor-specified)"},
            ],
        }

    def field_options(self, country=""):
        """国别变化时刷新选择项（本币名称与 10Y 利率）。"""
        return {"ok": True, "options": self._field_options(str(country or ""))}

    def _compute_with_live(self, params):
        """注入联机 WACC 取数；信用利差依赖 DSCR，迭代至稳定。"""
        live = self._live()
        countries = live.get("countries") or {}
        country = str(params.get("wacc_country", ""))
        c = countries.get(country) or {}
        if c:
            params["crp"] = float(c.get("crp") or params["crp"])
            params["country_def_spread"] = float(c.get("ds") or 0.0)
        sect = live.get("sectors") or {}
        bu = sect.get(str(params.get("wacc_sector", "")))
        if bu is not None:
            params["beta_u"] = float(bu)
        params["erp"] = float(live.get("erp") or params["erp"])
        params["risk_free_rate_usd"] = float(
            live.get("rf_usd") or params["risk_free_rate_usd"])
        params["risk_free_rate_cny"] = float(
            live.get("rf_cny") or params["risk_free_rate_cny"])
        # 本国货币 10Y 随国别自动取数（网页版同口径），不做人工填报；
        # 无本币基准时置 0，由引擎回落美元 Rf。
        local_rf = WD.local_rf_of(country) if country else None
        params["risk_free_rate_local"] = (float(local_rf) / 100.0
                                          if local_rf is not None else 0.0)
        rating = str(c.get("rating") or "")
        cs = float(params.get("credit_spread") or 0.0)
        for _ in range(4):
            params["credit_spread"] = cs
            m = E.compute(**params)
            nxt = WD.credit_spread(float(m["metrics"]["min_dscr"]), rating) / 100.0
            if abs(nxt - cs) < 5e-6:
                break
            cs = nxt
        return m

    # ── 元数据 ────────────────────────────────────────────────────────
    def schema(self):
        groups = [
            {"title": title, "title_en": en(title),
             "fields": [{"key": k, "label": lab, "label_en": en(lab),
                         "kind": kind, "unit": unit,
                         "unit_en": en(unit) if en(unit) else unit,
                         "hint": (FIELD_HINTS.get(k) or ("", ""))[0],
                         "hint_en": (FIELD_HINTS.get(k) or ("", ""))[1]}
                        for k, lab, kind, unit in fields]}
            for title, fields in GROUPS
        ]
        tables = [{"name": name, "name_en": en(name),
                   "type": "series",
                   "cols": [t for _, t, _, _ in spec],
                   "cols_en": en_list([t for _, t, _, _ in spec]),
                   "kinds": [kd for _, _, _, kd in spec]}
                  for name, spec in TABLE_SPECS]
        tables += [{"name": name, "name_en": en(name), "type": kind}
                   for name, kind in SPECIAL_TABLES]
        return {
            "appName": APP_NAME,
            "version": APP_VERSION,
            "buildStamp": _build_stamp(),
            "groups": groups,
            "choices": {k: list(labs) for k, (labs, _) in CHOICES.items()},
            "choicesEn": {k: en_list(labs) for k, (labs, _) in CHOICES.items()},
            "fieldOptions": self._field_options(
                str(E.DEFAULTS.get("wacc_country", ""))),
            "defaults": self._display_all({**E.DEFAULTS, **E.SCENARIOS["基准"]}),
            "cards": [{"key": k, "label": lab, "label_en": en(lab),
                       "kind": kind, "cat": cat, "cat_en": en(cat),
                       "unit": CARD_UNITS.get(k, ""),
                       "unit_en": en(CARD_UNITS.get(k, ""))}
                      for k, lab, kind, cat in CARD_DEFS],
            "tables": tables,
            "rules": [{"key": k, "driver": d, "values": list(v)}
                      for k, d, v in FIELD_RULES],
            "disableRules": [{"key": k, "driver": d, "values": list(v)}
                             for k, d, v in FIELD_DISABLE],
            "notes": FIELD_NOTES,
            "notesEn": NOTES_EN,
            "scenarios": ["基准", "保守", "乐观"],
            "scenariosEn": en_list(["基准", "保守", "乐观"]),
            "derivedFields": {g: [{"key": k, "label": lab, "label_en": en_lab,
                                   "unit": unit, "unit_en": en(unit), "under": under,
                                   "hint": hint, "hint_en": hint_en}
                                  for k, lab, en_lab, unit, under, hint, hint_en in fs]
                              for g, fs in DERIVED_FIELDS.items()},
        }

    def _display_all(self, params):
        out = {}
        for k in (f[0] for _, fields in GROUPS for f in fields):
            if k not in params:
                continue
            v = display_value(k, params[k])
            # 储能上网电价：0 表示跟随保障收购电价，界面留空并显示占位提示
            if k == "storage_elec_price" and abs(float(params[k] or 0.0)) < 1e-12:
                v = ""
            out[k] = v
        return out

    def preset(self, name):
        if name not in E.SCENARIOS:
            return {"ok": False, "error": f"未知情景：{name}"}
        values = self._display_all({**E.DEFAULTS, **E.SCENARIOS[name]})
        values["scenario"] = name
        return {"ok": True, "values": values}

    def defaults(self):
        values = self._display_all({**E.DEFAULTS, **E.SCENARIOS["基准"]})
        values["scenario"] = "基准"
        return {"ok": True, "values": values}

    # ── WACC 联网数据 ─────────────────────────────────────────────────
    def wacc_data(self, force=False):
        self.live = res_wacc.live_data(force=bool(force))
        return self.live

    # ── 计算 ──────────────────────────────────────────────────────────
    def compute(self, raw):
        if g := self._gate():
            return g
        t0 = time.time()
        try:
            params = coerce_params(raw)
            m = self._compute_with_live(params)
        except Exception as ex:
            return {"ok": False, "error": f"{type(ex).__name__}: {ex}"}

        self.last = (m, params)
        # 计价货币换算（仅显示层，模型内部始终为人民币）
        _ccy_raw = str(params.get("display_ccy") or "CNY")
        _ccy = _ccy_raw if _ccy_raw in CCY_CODES else "CNY"
        # 显示倍数：人民币金额 ÷ 1 单位目标货币折人民币 = 目标货币金额
        _scale = 1.0 if _ccy == "CNY" else 1.0 / self._ccy_scaler(_ccy)
        _meta = CCY_MAP.get(_ccy, CCY_MAP["CNY"])
        _munit, _munit_en = _meta["cn"], _meta["en"]
        km = dict(m["metrics"])
        km["unit_cost_w"] = km["unit_cost"] / 1000.0
        km["total_investment"] = m["p"]["total_investment"]
        km["station_invest"] = m["p"]["station_invest"]
        km["storage_invest"] = m["p"]["storage_invest"]
        km["equity_total"] = m["equity"]

        cards = [{"key": k, "label": lab, "label_en": en(lab),
                  "cat": cat, "cat_en": en(cat), "unit": CARD_UNITS.get(k, ""),
                  "unit_en": en(CARD_UNITS.get(k, "")),
                  "unit": _ccy_unit(CARD_UNITS.get(k, ""), _munit, _ccy != "CNY", _meta["prefix"]),
                  "unit_en": _ccy_unit_en(CARD_UNITS.get(k, ""), _munit_en, _ccy != "CNY", _meta["prefix"]),
                  "text": _fmt_card(km.get(k) * _scale
                                    if _is_money_unit(CARD_UNITS.get(k, "")) else km.get(k), kind)}
                 for k, lab, kind, cat in CARD_DEFS]

        extra = build_extra(m)
        tables = {}
        for name, spec in TABLE_SPECS:
            rows = []
            for i in range(m["n"]):
                rows.append({
                    "k": int(m["k"][i]),
                    "cells": [fmt_cell(resolve_value(m, extra, src, i) * _scale
                                       if src not in NON_MONEY_SRC else resolve_value(m, extra, src, i), kind)
                              for src, _, _, kind in spec],
                })
            tables[name] = {"type": "series", "name_en": en(name),
                            "cols": [t for _, t, _, _ in spec],
                            "cols_en": en_list([t for _, t, _, _ in spec]),
                            "kinds": [kd for _, _, _, kd in spec],
                            "rows": rows}

        live = self._live()
        tables["术语表"] = build_glossary()
        tables["决策信息模版"] = build_decision(m, money_scale=_scale, money_unit=_munit,
                                        price_scale=_scale, price_prefix=_meta["prefix"])
        tables["LCOE计算表"] = build_lcoe(m)
        tables["WACC计算表"] = build_wacc_pack(m, live)

        i0 = m["t"]
        first = []
        if i0 < m["n"]:
            interest = float(m["interest"][i0]) + float(m["wc_int"][i0])
            for label, v in (("营业收入", m["revenue"][i0]),
                             ("经营成本", m["opex"][i0]),
                             ("折旧", m["dep"][i0]),
                             ("利息", interest),
                             ("还本", m["principal"][i0]),
                             ("所得税", m["tax"][i0])):
                first.append({"label": label, "label_en": en(label),
                              "value": round(float(v), 1)})

        return {
            "ok": True,
            "elapsed": round(time.time() - t0, 3),
            "cards": cards,
            "summary": {
                "construct": int(m["t"]),
                "operate": int(m["a"]),
                "investment": round(float(m["p"]["total_investment"]) * _scale, 1),
                "equity": round(float(m["equity"]) * _scale, 1),
                "debt": round(float(m["debt"]) * _scale, 1),
                "wacc": float(km["wacc_capm"]),
                "genType": m["p"]["gen_type"],
            },
            "firstYear": first,
            "derived": build_derived(m, _scale, _munit, _munit_en),
            "ccy": {"code": _ccy, "unit": _munit, "unit_en": _munit_en,
                    "prefix": _meta["prefix"], "rate": round(_scale, 6)},
            "tables": tables,
            "waccLive": live,
            "waccInfo": {
                "country": params.get("wacc_country", ""),
                "sector": params.get("wacc_sector", ""),
                "ccy": params.get("wacc_ccy", ""),
                "betaU": round(float(params["beta_u"]), 4),
                "erp": round(float(params["erp"]), 6),
                "crp": round(float(params["crp"]), 6),
                "rf": round(float(m["p"]["risk_free_rate"]), 6),
                "cds": round(float(params.get("country_def_spread", 0.0)), 6),
                "creditSpread": round(float(params.get("credit_spread", 0.0)), 6),
                "rd": round(float(m["p"]["wacc_rd"]), 6),
                "wacc": round(float(km["wacc_capm"]), 8),
            },
            "chart": {
                "yr": [int(v) for v in m["yr"]],
                "k": [int(v) for v in m["k"]],
                "cum_p": [_num(v) for v in extra["cum_p"]],
                "cum_e": [_num(v) for v in extra["cum_e"]],
                "cf_project": [_num(v) for v in m["cf_project"]],
                "revenue": [_num(v) for v in m["revenue"]],
                "opex": [_num(v) for v in m["opex"]],
                "t": int(m["t"]),
            },
        }

    def scenarios(self, raw):
        if g := self._gate():
            return g
        try:
            base = coerce_params(raw)
        except Exception as ex:
            return {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
        rows = []
        for name in ("基准", "保守", "乐观"):
            params = {**base, **E.SCENARIOS[name], "scenario": name}
            try:
                m = self._compute_with_live(params)
            except Exception as ex:
                return {"ok": False, "error": f"{name}: {type(ex).__name__}: {ex}"}
            k = m["metrics"]
            rows.append({
                "name": name,
                "name_en": en(name),
                "pirr": fmt_pct(k["project_irr"]),
                "eirr": fmt_pct(k["equity_irr"]),
                "npv": fmt_num(k["project_npv"], 0),
                "enpv": fmt_num(k["equity_npv"], 0),
                "lcoe": fmt_num(k["lcoe"], 4),
                "dscr": fmt_num(k["min_dscr"], 2),
                "payback": fmt_num(k["project_payback"], 1),
            })
        return {"ok": True, "rows": rows}

    # ── 授权 ──────────────────────────────────────────────────────────
    def _gate(self):
        st = self.license.status()
        if st.get("licensed"):
            return None
        return {"ok": False, "gated": True, "license": st}

    def license_status(self):
        st = self.license.status()
        if st.get("enabled"):
            st["device_hash"] = self.license.device_hash()
            try:
                st["machine_code"] = self.license.machine_code()
            except Exception:
                st["machine_code"] = st["device_hash"][:16].upper()
            lic = st.get("license") or {}
            if lic.get("order_id"):
                st["order_id"] = lic["order_id"]
        return {"ok": True, **st}

    def license_plans(self):
        return {"ok": True, "plans": self.license.plans()}

    def license_buy(self, plan_id):
        return self.license.buy(str(plan_id))

    def license_poll(self, order_id):
        return self.license.poll(str(order_id))

    def license_restore(self, order_id):
        return self.license.restore(str(order_id))

    def license_transfer(self, key):
        """换机：订单号（ord_…）走订单迁移；其余按客户邮箱迁移。"""
        v = str(key or "").strip()
        if v.startswith("ord_"):
            return self.license.transfer(v)
        return self.license.transfer_by_email(v)

    def machine_code(self):
        try:
            return self.license.machine_code()
        except Exception:
            return ""

    def quit(self):
        if self.window is not None:
            self.window.destroy()

    # ── 导出 ──────────────────────────────────────────────────────────
    # ── 测算记录（历史保存 + 关闭前自动续存） ─────────────────────
    def _profile_dir(self):
        base = os.path.join(os.path.expanduser("~"),
                            "Library", "Application Support", "RES Financial Model")
        d = os.path.join(base, "profiles")
        os.makedirs(d, exist_ok=True)
        return d

    def _last_path(self):
        return os.path.join(self._profile_dir(), "_last_session.json")

    def profiles(self):
        """列出已保存的测算记录，按保存时间倒序。"""
        items = []
        for fn in os.listdir(self._profile_dir()):
            if not fn.endswith(".json") or fn.startswith("_"):
                continue
            try:
                with open(os.path.join(self._profile_dir(), fn), encoding="utf-8") as f:
                    d = json.load(f)
                items.append({"id": fn[:-5], "name": d.get("name", fn[:-5]),
                              "savedAt": d.get("savedAt", "")})
            except Exception:
                continue
        items.sort(key=lambda x: x["savedAt"], reverse=True)
        return {"ok": True, "items": items}

    def save_profile(self, name, values):
        """手动命名保存当前参数。同名则覆盖。"""
        nm = (name or "").strip()
        if not nm:
            return {"ok": False, "error": "名称不能为空"}
        safe = "".join(c for c in nm if c not in '\\/:*?"<>|').strip() or "记录"
        pid = safe
        path = os.path.join(self._profile_dir(), pid + ".json")
        rec = {"name": nm, "savedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "version": APP_VERSION, "values": dict(values or {})}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=1)
        return {"ok": True, "id": pid, "item": {"id": pid, "name": nm,
                                                "savedAt": rec["savedAt"]}}

    def load_profile(self, pid):
        path = os.path.join(self._profile_dir(), str(pid) + ".json")
        if not os.path.exists(path):
            return {"ok": False, "error": "记录不存在"}
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        return {"ok": True, "name": d.get("name", pid), "values": d.get("values", {})}

    def delete_profile(self, pid):
        path = os.path.join(self._profile_dir(), str(pid) + ".json")
        if os.path.exists(path):
            os.remove(path)
        return {"ok": True}

    def autosave(self, values):
        """关闭前/变更后自动续存，下次打开直接恢复。"""
        try:
            with open(self._last_path(), "w", encoding="utf-8") as f:
                json.dump({"savedAt": datetime.datetime.now().isoformat(timespec="seconds"),
                           "values": dict(values or {})}, f, ensure_ascii=False)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def last_session(self):
        p = self._last_path()
        if not os.path.exists(p):
            return {"ok": False}
        try:
            with open(p, encoding="utf-8") as f:
                d = json.load(f)
            return {"ok": True, "values": d.get("values", {}), "savedAt": d.get("savedAt", "")}
        except Exception:
            return {"ok": False}

    # ── 项目文件：另存为 / 打开（.resmodel，本质是 JSON） ─────────────
    def save_to_file(self, values):
        """弹系统保存框，把当前参数写成一个项目文件。"""
        if self.window is None:
            return {"ok": False, "error": "窗口未就绪"}
        try:
            import webview
            path = self.window.create_file_dialog(
                webview.SAVE_DIALOG, directory=os.path.expanduser("~/Desktop"),
                save_filename="RES 测算项目.resmodel")
        except Exception as e:
            return {"ok": False, "error": f"保存对话框失败：{e}"}
        if not path:
            return {"ok": False, "cancelled": True}
        path = path if isinstance(path, str) else path[0]
        if not path.endswith(".resmodel"):
            path += ".resmodel"
        rec = {"app": APP_NAME, "version": APP_VERSION,
               "savedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "values": dict(values or {})}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=1)
        except Exception as e:
            return {"ok": False, "error": f"写入失败：{e}"}
        self._current_path = path
        return {"ok": True, "path": path, "name": os.path.basename(path)}

    def save_current(self, values):
        """直接覆盖当前已命名的文件；没命名过则提示另存为。"""
        path = self._current_path
        if not path:
            return {"ok": False, "error": "还没有命名文件，请先「另存为」"}
        rec = {"app": APP_NAME, "version": APP_VERSION,
               "savedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "values": dict(values or {})}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(rec, f, ensure_ascii=False, indent=1)
        except Exception as e:
            return {"ok": False, "error": f"写入失败：{e}"}
        return {"ok": True, "path": path, "name": os.path.basename(path),
                "savedAt": rec["savedAt"]}

    def current_file(self):
        return {"ok": True, "path": self._current_path,
                "name": os.path.basename(self._current_path) if self._current_path else ""}

    def open_file(self):
        """弹打开框，读回项目文件里的参数。"""
        if self.window is None:
            return {"ok": False, "error": "窗口未就绪"}
        try:
            import webview
            sel = self.window.create_file_dialog(
                webview.OPEN_DIALOG, directory=os.path.expanduser("~/Desktop"),
                allow_multiple=False,
                file_types=("RES 项目文件 (*.resmodel;*.json)", "所有文件 (*.*)"))
        except Exception as e:
            return {"ok": False, "error": f"打开对话框失败：{e}"}
        if not sel:
            return {"ok": False, "cancelled": True}
        path = sel if isinstance(sel, str) else sel[0]
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
        except Exception as e:
            return {"ok": False, "error": f"读取失败：{e}"}
        if "values" not in d:
            return {"ok": False, "error": "不是本模型的项目文件"}
        self._current_path = path
        return {"ok": True, "path": path, "name": os.path.basename(path),
                "values": d["values"], "savedAt": d.get("savedAt", "")}

    # ── 敏感度分析（按需计算，不参与每次重算）────────────────────
    SENS_DRIVERS = [
        ("电价（PPA）", "Price (PPA)", "benchmark_tariff"),
        ("电站 EPC 单价", "Station EPC unit price", "epc_price_station"),
        ("首年发电小时", "First-year hours", "actual_gen_hours"),
        ("储能配置比例", "Storage ratio", "storage_ratio"),
        ("储能 EPC 单价", "Storage EPC unit price", "storage_unit_price"),
        ("项目前期开发费", "Pre-development cost", "predev_price_per_w"),
        ("债务比例", "Debt ratio", "debt_ratio"),
        ("债务利率", "Debt interest rate", "debt_rate"),
        ("增值税率", "VAT rate", "vat_rate"),
        ("人均年薪", "Average salary", "avg_salary"),
        ("运维其他费用", "Other O&M cost", "other_cost_rate"),
        ("土地年租金", "Land rent", "land_rent_usd"),
    ]

    def sensitivity(self, raw):
        try:
            params = coerce_params(raw)
        except Exception as ex:
            return {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
        rows = []
        try:
            for cn, en_, key in self.SENS_DRIVERS:
                base_v = float(params.get(key) or 0.0)
                if abs(base_v) < 1e-12:
                    continue
                cells = []
                for f in (0.9, 1.0, 1.1):
                    pp = dict(params)
                    pp[key] = base_v * f
                    mm = self._compute_with_live(pp)
                    met = mm["metrics"]
                    cells.append({"irr": float(met["project_irr"]),
                                  "mirr": float(met.get("mirr_project", float("nan"))),
                                  "eq_irr": float(met.get("equity_irr", float("nan"))),
                                  "npv": float(met["project_npv"]),
                                  "dscr": float(met["min_dscr"])})
                rows.append({"label": cn, "label_en": en_, "base": base_v, "cells": cells})
        except Exception as ex:
            return {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
        return {"ok": True, "levels": ["−10%", "基准 Base", "+10%"], "rows": rows}

    # ── 借款期限敏感性（全投资/资本金 × IRR/MIRR/DSCR）────────────
    TERM_LEVELS = (5, 8, 10, 12, 15, 18, 20)

    def term_sensitivity(self, raw):
        try:
            params = coerce_params(raw)
        except Exception as ex:
            return {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
        rows = []
        try:
            for term in self.TERM_LEVELS:
                pp = dict(params)
                pp["debt_tenor"] = int(term)
                mm = self._compute_with_live(pp)
                met = mm["metrics"]
                rows.append({
                    "term": term,
                    "pirr": float(met["project_irr"]),
                    "pmirr": float(met.get("mirr_project", float("nan"))),
                    "eirr": float(met.get("equity_irr", float("nan"))),
                    "emirr": float(met.get("mirr_equity", float("nan"))),
                    "dscr": float(met.get("min_dscr", float("nan"))),
                })
        except Exception as ex:
            return {"ok": False, "error": f"{type(ex).__name__}: {ex}"}
        return {"ok": True, "rows": rows}

    # ── 实时汇率（USD 基准，缓存 30 分钟）──────────────────────
    def _fx_table(self, force=False):
        import urllib.request as _u
        now = time.time()
        if not force and self._fx and (now - self._fx_ts) < 1800:
            return self._fx
        try:
            req = _u.Request("https://open.er-api.com/v6/latest/USD",
                             headers={"User-Agent": "curl/8.0"})
            with _u.urlopen(req, timeout=6) as r:
                d = json.load(r)
            rates = d.get("rates") or {}
            if float(rates.get("CNY") or 0) > 0:
                self._fx, self._fx_ts, self._fx_src = rates, now, "live"
                return rates
        except Exception:
            pass
        if self._fx and self._fx_src == "live":
            return self._fx
        self._fx = {"CNY": float(E.DEFAULTS.get("exchange_rate", 7.0)) or 7.0, "USD": 1.0}
        self._fx_src = "fallback"
        return self._fx

    def i18n(self, lang="zh"):
        """返回界面语言包（中文 → 译文）；没有语言包时返回空表，前端回落中英文。"""
        code = str(lang or "zh").strip().lower()
        if code in ("", "zh"):
            return {"ok": True, "lang": "zh", "table": {}}
        path = asset_path("web", "i18n", f"{code}.json")
        if not os.path.exists(path):
            return {"ok": True, "lang": "zh", "table": {}, "fallback": True}
        try:
            with open(path, encoding="utf-8") as f:
                table = json.load(f)
            return {"ok": True, "lang": code, "table": table}
        except Exception:
            return {"ok": True, "lang": "zh", "table": {}, "fallback": True}

    def fx_rate(self, force=False):
        rates = self._fx_table(force=bool(force))
        cny = float(rates.get("CNY") or 7.0)
        return {"ok": True, "rates": rates, "source": self._fx_src or "fallback",
                "usd_cny": round(cny, 4), "note": f"1 美元 = {cny:,.4f} 元"}

    def _ccy_scaler(self, code):
        """1 单位目标货币 = 多少人民币。"""
        rates = self._fx_table()
        cny = float(rates.get("CNY") or 7.0)
        r = float(rates.get(code) or 0.0)
        if code == "CNY" or r <= 0:
            return 1.0 if code == "CNY" else cny
        return cny / r

    def export(self, lang="bi", tables=None, langs=None):
        if g := self._gate():
            return g
        if self.last is None:
            return {"ok": False, "error": "尚未计算"}
        if self.window is None:
            return {"ok": False, "error": "窗口未就绪"}
        lang = lang if lang in LANGS else "bi"
        if lang == "pair" and not langs:
            _pr = (self.last[1] if self.last else {}) or {}
            def _code(v, d):
                v = str(v or "")
                m = __import__("re").search(r"\(([A-Za-z-]{2,5})\)$", v)
                if m:
                    return m.group(1)
                return "none" if "无" in v else d
            langs = [_code(_pr.get("ui_lang"), "zh"), _code(_pr.get("ui_lang2"), "en")]
        if isinstance(tables, str):
            tables = [tables]
        tables = [t for t in (tables or ALL_SHEETS) if t]
        unknown = [t for t in tables if t not in ALL_SHEETS]
        if unknown:
            return {"ok": False, "error": "未知表格：" + "、".join(unknown)}
        if len(tables) == 1:
            part = SHEET_EN.get(tables[0], tables[0]).replace(" ", "_")
        elif len(tables) < len(ALL_SHEETS):
            part = "Selected_Tables"
        else:
            part = "All_Tables"
        tags = {"bi": "Bilingual", "en": "English",
                "zh-CN": "Simplified_Chinese", "zh-TW": "Traditional_Chinese"}
        default = f"RES_Financial_Model_{part}_{datetime.date.today():%Y%m%d}_{tags[lang]}.xlsx"
        desktop = os.path.expanduser("~/Desktop")
        try:
            import webview
            picked = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=desktop if os.path.isdir(desktop) else os.path.expanduser("~"),
                save_filename=default,
                file_types=("Excel 工作簿 (*.xlsx)",))
        except Exception as ex:
            return {"ok": False, "error": f"打开保存对话框失败：{ex}"}
        if not picked:
            return {"ok": False, "cancelled": True}
        path = picked[0] if isinstance(picked, (list, tuple)) else picked
        if not str(path).lower().endswith(".xlsx"):
            path = str(path) + ".xlsx"
        m, params = self.last
        try:
            export_workbook(m, params, path, live=self.live, lang=lang, tables=tables)
        except Exception as ex:
            return {"ok": False, "error": f"导出失败：{type(ex).__name__}: {ex}"}
        return {"ok": True, "path": str(path), "lang": lang}


# ── 自检（无需窗口）───────────────────────────────────────────────────
def selftest():
    api = Api(res_license.Client(enabled=False))
    api.live = res_wacc.live_data(force=False)     # 只读快照/兜底，不联网
    sc = api.schema()
    assert len(sc["groups"]) == 11, len(sc["groups"])
    assert len(sc["tables"]) == len(ALL_TABLE_NAMES), len(sc["tables"])
    assert len(sc["cards"]) == len(CARD_DEFS)

    payload = api.compute(sc["defaults"])
    assert payload["ok"], payload.get("error")
    n = len(payload["chart"]["yr"])
    for name, _ in TABLE_SPECS:
        assert len(payload["tables"][name]["rows"]) == n, name
    for name in ("决策信息模版", "LCOE计算表", "WACC计算表"):
        assert name in payload["tables"], name
    assert [s["title"] for s in payload["tables"]["WACC计算表"]["sections"]] == [
        "WACC 计算过程", "WACC 三币种对比", "WACC 敏感度"]
    def dec_text(tbl):
        return " ".join(c.get("t", "") for block in tbl["blocks"]
                        for row in block for c in row["cells"])

    pv_txt = dec_text(payload["tables"]["决策信息模版"])
    for needle in ("1 项目测算情况", "2 建设期利息和业主管理费",
                   "3 前期开发阶段", "4 EPC 总包工程部分", "光伏组件",
                   "其他 Others", "结余 balance"):
        assert needle in pv_txt, needle
    assert pv_txt.count("其他 Others") == 1, "Others must be the single balancing row"
    assert "其他（可调）" not in pv_txt
    assert "风力发电" not in pv_txt and "风电机组" not in pv_txt

    subs = [cell for block in payload["tables"]["决策信息模版"]["blocks"]
            for row in block if row.get("cls") == "subtotal"
            for cell in row["cells"] if cell.get("sub")]
    assert [c["sub"] for c in subs] == ["s1", "s2", "s3", "s4"], subs

    wind = dict(sc["defaults"])
    wind["gen_type"] = "风电"
    wp = api.compute(wind)
    assert wp["ok"], wp.get("error")
    wind_txt = dec_text(wp["tables"]["决策信息模版"])
    assert "风电机组" in wind_txt and "光伏组件" not in wind_txt, wind_txt[:200]

    rows = api.scenarios(sc["defaults"])
    assert rows["ok"] and len(rows["rows"]) == 3, rows

    m, params = api.last
    path = os.path.join(tempfile.mkdtemp(), "selftest.xlsx")
    export_workbook(m, params, path, live=api.live)
    from openpyxl import load_workbook
    wb = load_workbook(path, data_only=True)
    expect = [SHEET_EN[n] for n in ["参数", "核心指标"] + ALL_TABLE_NAMES]
    assert wb.sheetnames == expect, wb.sheetnames
    for name, _ in TABLE_SPECS:
        assert wb[SHEET_EN[name]].max_row == n + 1, (name, wb[SHEET_EN[name]].max_row)
    for lang in ("bi", "en", "zh-CN", "zh-TW"):
        path2 = os.path.join(tempfile.mkdtemp(), f"selftest_{lang}.xlsx")
        export_workbook(m, params, path2, live=api.live, lang=lang,
                        tables=["核心指标", "损益表"])
        wb2 = load_workbook(path2, data_only=True)
        assert wb2.sheetnames == [SHEET_EN["核心指标"], SHEET_EN["损益表"]], \
            (lang, wb2.sheetnames)
        if lang == "zh-TW":
            assert wb2[SHEET_EN["核心指标"]]["A1"].value == "指標", \
                "OpenCC 繁体转换不可用"
        km = wb2[SHEET_EN["核心指标"]]
        npv = next(float(km.cell(r, 2).value) for r in range(2, km.max_row + 1)
                   if "NPV" in str(km.cell(r, 1).value))
        scale = 10.0 if lang in ("en", "zh-TW") else 1.0
        assert abs(npv - round(m["metrics"]["project_npv"] * scale, 2)) < .01, \
            (lang, "货币换算不符", npv)
        if lang == "en":
            texts = [str(c.value) for ws in wb2.worksheets
                     for row in ws.iter_rows() for c in row
                     if isinstance(c.value, str)]
            assert not any(any("一" <= ch <= "鿿" for ch in t)
                           for t in texts), "英文版残留中文"
        if lang in ("en", "zh-TW"):
            assert not any(
                "万元" in str(c.value) or "萬元" in str(c.value)
                for ws in wb2.worksheets for row in ws.iter_rows()
                for c in row if isinstance(c.value, str)), \
                (lang, "英文/繁体版残留「万元」")
        os.remove(path2)
    wb_raw = load_workbook(path, data_only=False)
    assert not any(
        c.data_type == "f"
        for ws in wb_raw.worksheets
        for row in ws.iter_rows()
        for c in row
    ), "导出的工作簿不得包含公式单元格"
    os.remove(path)

    for f in ("index.html", "app.css", "app.js"):
        assert os.path.exists(asset_path("web", f)), f

    irr = next(c["text"] for c in payload["cards"] if c["key"] == "project_irr")
    try:
        print("SELFTEST OK", f"IRR={irr}", f"rows={n}",
              f"tables={len(ALL_TABLE_NAMES)}", f"cards={len(CARD_DEFS)}")
    except Exception:
        pass  # windowed (no-console) builds have no stdout


# ── 本机握手：只对本机网页（resmodel.com）回答「这台机器已授权」 ──────────
HANDSHAKE_PORTS = range(47653, 47661)
HANDSHAKE_ORIGINS = ("https://resmodel.com", "https://www.resmodel.com")


def start_handshake_server(client, ports=HANDSHAKE_PORTS):
    """在 127.0.0.1 起一个只读小服务，供同机浏览器验证授权。返回端口或 0。"""
    import http.server
    import json as _json
    import socketserver
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "RESHandshake/1.0"

        def _cors(self):
            origin = self.headers.get("origin", "")
            ok = origin in HANDSHAKE_ORIGINS or origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")
            if ok:
                self.send_header("access-control-allow-origin", origin)
                self.send_header("vary", "origin")
            self.send_header("access-control-allow-headers", "content-type")
            self.send_header("access-control-allow-methods", "GET, OPTIONS")
            self.send_header("access-control-allow-private-network", "true")
            self.send_header("cache-control", "no-store")

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            if self.path.split("?")[0] != "/handshake":
                self.send_error(404)
                return
            try:
                st = client.status()
                lic = {
                    "licensed": bool(st.get("licensed")),
                    "plan_id": (st.get("plan_id") or (st.get("license") or {}).get("plan_id") or ""),
                    "expires_at": (st.get("license") or {}).get("expires_at"),
                }
                body = _json.dumps({
                    "v": 1,
                    "app": APP_NAME,
                    "machine_code": client.machine_code(),
                    "device_hash": client.device_hash(),
                    "licensed": lic["licensed"],
                    "plan_id": lic["plan_id"],
                    "expires_at": lic["expires_at"],
                    "token": client.raw_token(),
                }).encode("utf-8")
            except Exception as ex:
                body = _json.dumps({"v": 1, "error": str(ex)}).encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "application/json; charset=utf-8")
            self._cors()
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

    for port in ports:
        try:
            srv = Server(("127.0.0.1", port), Handler)
        except OSError:
            continue
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return port
    return 0


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    import webview
    lic = res_license.Client(enabled=_license_enabled(), app_version=APP_VERSION)
    api = Api(lic)
    window = webview.create_window(
        f"{APP_NAME}",
        url=asset_path("web", "index.html"),
        js_api=api,
        width=1460,
        height=940,
        min_size=(1180, 720),
        background_color="#eef2f6",
    )
    api.window = window
    lic.start()
    if getattr(lic, "enabled", False):
        try:
            _p = start_handshake_server(lic)
            if _p:
                print(f"[handshake] 127.0.0.1:{_p}")
        except Exception as _e:
            print(f"[handshake] disabled: {_e}")
    webview.start()
    lic.stop()


if __name__ == "__main__":
    main()
