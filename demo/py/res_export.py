#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一次计算结果导出为 Excel 工作簿（每张表一个 tab，可选语言与表格子集）。"""
import re

import numpy as np

from res_schema import (GROUPS, CHOICES, TABLE_SPECS, build_extra,
                        resolve_value, param_kind,
                        build_glossary, build_decision, build_lcoe, build_wacc,
                        build_wacc_pack, build_wacc_compare, build_wacc_sens,
                        en, en_list)

LANGS = ("bi", "en", "zh-CN", "zh-TW", "pair")
_I18N_CACHE = {}


def _i18n_table(code):
    """读取 web/i18n/<code>.json（中文→译文）；没有则返回空表。"""
    if code in _I18N_CACHE:
        return _I18N_CACHE[code]
    import json as _json, os as _os
    path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "web", "i18n", f"{code}.json")
    table = {}
    if _os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                table = _json.load(f)
        except Exception:
            table = {}
    _I18N_CACHE[code] = table
    return table


def _text_in(code, s):
    """把中文串翻成指定语言代码；无译文回落英文、再回落中文。"""
    if code in ("", "zh", "zh-CN"):
        return s
    if code == "en":
        return en(s) or s
    return _i18n_table(code).get(s) or en(s) or s
LANG_TAGS = {"bi": "中英对照", "en": "EN", "zh-CN": "简体", "zh-TW": "繁體"}

SHEET_EN = {
    "参数": "Parameters",
    "核心指标": "Key Metrics",
    "损益表": "Income Statement",
    "全部投资现金流": "Project Cash Flow",
    "资本金现金流": "Equity Cash Flow",
    "还本付息表": "Debt Service",
    "销售收入": "Revenue",
    "增值税计算表": "VAT Calculation",
    "资产负债表": "Balance Sheet",
    "总成本表": "Total Costs",
    "资金筹措": "Funding",
    "折旧表": "Depreciation",
    "摊销表": "Amortisation",
    "财务计划": "Financial Plan",
    "术语表": "Glossary",
    "决策信息模版": "Decision Template",
    "LCOE计算表": "LCOE Calculation",
    "WACC计算表": "WACC Calculation",
}

ALL_SHEETS = (["参数", "核心指标"] + [n for n, _ in TABLE_SPECS]
              + ["术语表", "决策信息模版", "LCOE计算表", "WACC计算表"])

_CJK = re.compile(r"[㐀-鿿]")


def _has_cjk(s):
    return bool(_CJK.search(s))


def _pick_bilingual(s, lang):
    """从「中文行\\nEnglish line」里挑出对应语言；无对应行时返回 None。"""
    lines = [ln for ln in str(s).split("\n") if ln.strip()]
    if lang == "en":
        keep = [ln for ln in lines if not _has_cjk(ln)]
    else:
        keep = [ln for ln in lines if _has_cjk(ln)]
    return "\n".join(keep) if keep else None


_cc = None


def _to_tw(s):
    global _cc
    if _cc is None:
        try:
            from opencc import OpenCC
            _cc = OpenCC("s2t")
        except Exception:
            _cc = False
    return s if _cc is False else _cc.convert(s)


# 动态拼出的中英混排文案（WACC/LCOE/决策模版）在英文版里逐段替换
_EN_PHRASES = [
    ("βL 与 ERP/CRP 三币种共用；", "βL is shared across three currencies; "),
    ("Rf 取各币种 10Y 国债。", "Rf from each currency's 10Y sovereign. "),
    ("Rd 口径：", "Rd basis: "),
    ("取数：", "Source: "),
    ("吉尔吉斯斯坦索姆", "KGS"),
    ("吉尔吉斯斯坦", "Kyrgyzstan"),
    ("国别类别", "Country Category"),
    ("信用利差加成", "credit spread adder"),
    ("国别违约利差", "Country Default Spread"),
    ("信用利差", "Credit Spread"),
    ("合成评级法", "Synthetic Rating"),
    ("折现基准", "Discount Base"),
    ("折现率", "Discount Rate"),
    ("运营第一年", "first operating year"),
    ("运营期", "operating period"),
    ("人民币", "RMB"),
    ("美元", "USD"),
    ("本国货币", "local currency"),
    ("本模型未单列，含于电站 EPC", "Not separately modeled (within station EPC)"),
    ("本模型未单列", "Not modeled"),
    ("本模型", "this model"),
    ("对照", "reference"),
    ("10 年期国债", "10Y government bond"),
    ("成熟市场", "mature-market"),
    ("所选币种", "selected currency"),
    ("模型折现率", "model discount rate"),
    ("前期开发费（项目技术开发）Project Technology Development Fee",
     "Early Development Fee (Project Technology Development)"),
    ("所选币种 WACC", "selected-currency WACC"),
    ("（已作为模型折现率）", " (used as the model discount rate)"),
    ("已作为模型折现率", "used as the model discount rate"),
    ("三币种共用", "shared across three currencies"),
    ("三币种对比", "Currency Comparison"),
    ("WACC 计算过程", "WACC Calculation"),
    ("WACC 敏感度", "WACC Sensitivity"),
    ("DSCR 档", "DSCR tier"),
    ("债务成本", "cost of debt"),
    ("国别风险溢价", "country risk premium"),
    ("行业无杠杆贝塔取数口径", "Industry unlevered beta source"),
    ("再杠杆", "Relevered"),
    ("税后债务成本", "After-tax cost of debt"),
    ("所属行业", "Sector"),
    ("按第 3 项结余反推", "Back-solved from balance"),
    ("测算总投资", "Estimated total investment"),
    ("当收益率为", "When IRR ="),
    ("总投资为", "Total Investment ="),
    ("前期开发费（项目技术开发）", "Early Development Fee (Project Technology Development)"),
    ("建设期利息", "Interest during construction"),
    ("业主管理费", "Owner mgmt fee"),
    ("流动资金", "Working capital"),
    ("融资费", "Financing fee"),
    ("项目总投资", "Total Investment"),
    ("小计", "Subtotal"),
    ("结余", "balance"),
    ("为当前口径", "= current basis"),
    ("行＝", "Rows = "),
    ("列＝", "Columns = "),
    ("本地快照", "local snapshot"),
    ("数据日期", "data date"),
    ("抓取", "fetched"),
    ("金额", "Amount"),
    ("单价", "Unit Price"),
    ("备注", "Note"),
    ("内容", "Content"),
    ("编号", "No."),
    ("口径", "Basis"),
    ("（k/年）", "(k/yr)"),
    ("万元", "k"),
    ("亿kWh", "100M kWh"),
    ("元/kWh", "¥/kWh"),
    ("元/W", "¥/W"),
    ("前沿", "Frontier"),
    ("投机级", "Speculative"),
    ("投资级", "Investment Grade"),
]

_EN_EXTRA = {
    "参数": "Parameters", "取值": "Value", "最小 ICR": "Min ICR",
    "再杠杆 βL": "Relevered βL",
    "税后债务成本 Rd×(1−Tc)": "After-tax Cost of Debt Rd×(1−Tc)",
    "所选币种的 WACC 即模型折现率":
        "The selected currency's WACC is the model discount rate",
    "是（合成评级法）": "Yes (synthetic rating)",
    "总投资（万元）": "Total Investment (k)",
    "权益资金（万元）": "Equity (k)",
    "人民币 RMB": "RMB",
    "吉尔吉斯斯坦共和国600MW光伏发电项目":
        "Kyrgyz Republic 600MW Solar PV Project",
}


_UNIT_EN = {
    "年": "yrs",
    "万元/年": "k CNY/yr",
    "MW": "MW",
    "h/年": "h/yr",
    "h/年（0=自动）": "h/yr (0 = auto)",
    "%": "%",
    "%/年": "%/yr",
    "元/kWh": "CNY/kWh",
    "h": "h",
    "天/年": "days/yr",
    "元/Wh": "CNY/Wh",
    "人/100MWh": "staff/100MWh",
    "人/100MW": "staff/100MW",
    "元/MWh·年": "CNY/MWh·yr",
    "元/kW·年": "CNY/kW·yr",
    "元/kW(直流)": "CNY/kW (DC)",
    "万元": "k CNY",
    "元/kW": "CNY/kW",
    "%（末年末）": "% (final year-end)",
    "人/50MW": "staff/50MW",
    "万元/人·年": "k CNY/person·yr",
    "公顷": "ha",
    "美元/公顷·年": "USD/ha/yr",
    "元/美元": "CNY/USD",
    "元/平方米": "CNY/m²",
    "月": "months",
}

_EN_SORTED = sorted(_EN_PHRASES, key=lambda p: len(p[0]), reverse=True)


def _en_clean(s):
    out = str(s)
    # 原文自带英文时先合并「中文 English」，避免逐词替换后英文重复
    for cn, eng in _EN_SORTED:
        out = re.sub(re.escape(cn) + r"\s*" + re.escape(eng), eng, out,
                     flags=re.I)
    out = re.sub(r"运营期 (\d+) 年", r"operating period \1 years", out)
    for cn, eng in _EN_SORTED:
        out = out.replace(cn, eng)
    for a, b in (("　｜　", " | "), ("｜", " | "), ("；", "; "), ("，", ", "),
                 ("：", ": "), ("。", ". "), ("（", " ("), ("）", ") "),
                 ("＋", " + "), ("＝", " = "), ("　", " "), ("——", " — ")):
        out = out.replace(a, b)
    out = _CJK.sub("", out)
    out = re.sub(r"\(\s+", "(", out)
    out = re.sub(r"\s+\)", ")", out)
    out = re.sub(r"\s*;\s*", "; ", out)
    out = re.sub(r"\s{2,}", " ", out).strip(" ;,")
    return out if re.search(r"[0-9A-Za-z]", out) else str(s)


def _make_tr(lang, bi_cell):
    def tr(s, title=False):
        s = "" if s is None else str(s)
        if lang == "bi":
            return bi_cell(s) if title else s
        if lang == "en":
            e = en(s) or _EN_EXTRA.get(s)
            if e:
                return e.replace("¥10k", "k").replace("¥", "CNY")
            picked = _pick_bilingual(s, "en")
            out = _en_clean(picked if picked else s)
            return out.replace("¥10k", "k").replace("¥", "CNY")
        picked = _pick_bilingual(s, "zh-CN")
        s = picked or s
        return _to_tw(s) if lang == "zh-TW" else s

    return tr


def _sheet_name(name, lang):
    # tab 名一律英文（用户 2026-10-18 指定），与语言选项无关
    return SHEET_EN.get(name, name)


def export_workbook(m, params, path, live=None, lang="bi", tables=None, langs=None):
    from openpyxl import Workbook
    from openpyxl.styles import Border, Side, Font, PatternFill, Alignment

    lang = lang if lang in LANGS else "bi"
    wanted = {t for t in (tables or ALL_SHEETS)}
    unknown = wanted - set(ALL_SHEETS)
    if unknown:
        raise ValueError("未知表格：" + "、".join(sorted(unknown)))

    wb = Workbook()
    head_fill = PatternFill("solid", start_color="16324F")
    head_font = Font(color="FFFFFF", bold=True)
    sect_fill = PatternFill("solid", start_color="F0F4F8")
    sect_font = Font(bold=True, color="06141C")
    band_fill = PatternFill("solid", start_color="F7FAFC")
    banner_fill = PatternFill("solid", start_color="E8F4EE")
    banner_font = Font(bold=True, color="042010")
    line = Side(style="thin", color="DCE3EC")
    box = Border(left=line, right=line, top=line, bottom=line)

    def bi_cell(cn):
        e = en(cn)
        return f"{cn}\n{e}" if e and e != cn else cn

    def tr_pair(s, title=False):
        codes = [c for c in (langs or ["zh", "en"]) if c and c != "none"]
        parts = []
        for c in codes:
            t = _text_in(c, s)
            if t and t not in parts:
                parts.append(t)
        return "\n".join(parts)

    tr = tr_pair if (lang == "pair" and langs) else _make_tr(lang, bi_cell)

    # 英文/繁体版：货币值 ×10（1 万元 = 10 k），单位改用 k
    conv = lang in ("en", "zh-TW") and not (lang == "pair")
    mscale = 10.0 if conv else 1.0
    NON_MONEY_SRC = {
        "yr", "k", "dscr", "icr", "hours", "gen", "gen_guar", "gen_over",
        "gen_mkt", "gen_storage", "dep_rate", "amort_rate",
    }

    def is_money(src, kind):
        return kind in ("f1", "f4") and src not in NON_MONEY_SRC

    def money_head(title):
        t = tr(title, True)
        if not conv:
            return t
        return f"{t}（k）" if lang == "zh-TW" else f"{t} (k)"

    def new_sheet(name):
        ws = wb.create_sheet(_sheet_name(name, lang))
        ws.sheet_view.showGridLines = False
        return ws

    def style_header(ws, ncols, row=1):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=row, column=c)
            cell.fill = head_fill
            cell.font = head_font
            cell.alignment = Alignment(horizontal="center", wrap_text=True,
                                       vertical="center")
        ws.row_dimensions[row].height = 30

    def finish(ws, header_row=None, first_data=None, ncols=None):
        """统一加网格线、数字格式与隔行底色，贴近网页表格观感。"""
        max_r, max_c = ws.max_row, ws.max_column
        for r in range(1, max_r + 1):
            for c in range(1, max_c + 1):
                cell = ws.cell(row=r, column=c)
                cell.border = box
                v = cell.value
                if isinstance(v, bool):
                    continue
                if isinstance(v, int):
                    cell.number_format = "#,##0"
                elif isinstance(v, float):
                    cell.number_format = "#,##0.00"
                if header_row and first_data and r >= first_data and \
                        isinstance(v, (int, float)) and not isinstance(v, bool):
                    if (r - first_data) % 2 == 1:
                        cell.fill = band_fill

    # ── 参数 ──────────────────────────────────────────────────────────
    if "参数" in wanted:
        ws = new_sheet("参数")
        ws.append([tr("参数", True), tr("取值", True), tr("单位", True)])
        style_header(ws, 3)
        labels, punits = {}, {}
        for _, fields in GROUPS:
            for field in fields:
                key, label = field[0], field[1]
                labels[key] = tr(label, True)
                punits[key] = field[3] if len(field) > 3 else ""
        pct_keys = {k for k in params if param_kind(k) == "pct"}
        for key in sorted(params):
            val = params[key]
            unit = punits.get(key, "")
            money_conv = conv and unit.startswith("万元")
            if money_conv and isinstance(val, (int, float)):
                val = val * 10.0
            if lang == "en":
                unit_txt = _UNIT_EN.get(unit, unit)
            elif lang == "zh-TW":
                unit_txt = _to_tw(unit.replace("万元", "k") if money_conv else unit)
            else:
                unit_txt = unit
            if key in pct_keys:
                val = f"{float(val) * 100:.6g} %"
            if key in CHOICES:
                labs, mapping = CHOICES[key]
                lab = next((lab for lab in labs if str(mapping[lab]) == str(val)), val)
                if lang == "en":
                    val = en(str(lab)) or _EN_EXTRA.get(str(lab)) or \
                        _en_clean(str(lab))
                elif lang == "zh-TW":
                    val = _to_tw(str(lab))
                elif lang == "bi":
                    e = en(str(lab))
                    val = f"{lab} / {e}" if e else lab
                else:
                    val = str(lab)
            elif lang == "en" and isinstance(val, str):
                val = en(val) or _EN_EXTRA.get(val) or val
            ws.append([labels.get(key, key), val, unit_txt])
        ws.column_dimensions["A"].width = 36
        ws.column_dimensions["B"].width = 24
        ws.column_dimensions["C"].width = 18
        for r in range(2, ws.max_row + 1):
            ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True, vertical="center")
            ws.cell(row=r, column=2).alignment = Alignment(vertical="center")
            ws.cell(row=r, column=3).alignment = Alignment(vertical="center")
        finish(ws)

    # ── 核心指标 ──────────────────────────────────────────────────────
    if "核心指标" in wanted:
        ws = new_sheet("核心指标")
        ws.append([tr("指标", True), tr("数值", True)])
        style_header(ws, 2)
        k = m["metrics"]
        rows = [
            ("全投资 IRR（税后）", f"{k['project_irr'] * 100:.2f}%"),
            ("全投资 IRR（税前）", f"{k['project_irr_pretax'] * 100:.2f}%"),
            ("资本金 IRR", f"{k['equity_irr'] * 100:.2f}%"),
            ("全投资 NPV（万元）", k["project_npv"]),
            ("资本金 NPV（万元）", k["equity_npv"]),
            ("全投资回收期（年）", round(k["project_payback"], 2)),
            ("资本金回收期（年）", round(k["equity_payback"], 2)),
            ("LCOE（元/kWh）", round(k["lcoe"], 4)),
            ("最小 DSCR", round(k["min_dscr"], 3)),
            ("平均 DSCR", round(k["avg_dscr"], 3)),
            ("最小 ICR", round(k["min_icr"], 3)),
            ("平均 ICR", round(k["avg_icr"], 3)),
            ("折现率 WACC", f"{k['wacc_capm'] * 100:.2f}%"),
            ("单位造价（元/W）", round(k["unit_cost"] / 1000.0, 3)),
            ("平均 ROE", f"{k['avg_roe'] * 100:.2f}%"),
            ("峰值资产负债率", f"{k['peak_debt_ratio'] * 100:.2f}%"),
            ("总投资（万元）", m["p"]["total_investment"]),
            ("权益资金（万元）", m["equity"]),
            ("债务资金（万元）", m["debt"]),
            ("全期营业收入（万元）", k["total_revenue"]),
            ("全期经营成本（万元）", k["total_opex"]),
        ]
        for label, value in rows:
            if "（万元）" in label:
                value = round(float(value) * mscale, 2)
            t = tr(label, True)
            if conv and lang == "zh-TW":
                t = t.replace("萬元", "k").replace("万元", "k")
            ws.append([t, value])
        ws.column_dimensions["A"].width = 36
        ws.column_dimensions["B"].width = 20
        for r in range(2, ws.max_row + 1):
            ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True, vertical="center")
        finish(ws)

    # ── 年度报表 ──────────────────────────────────────────────────────
    extra = build_extra(m)
    for name, spec in TABLE_SPECS:
        if name not in wanted:
            continue
        ws = new_sheet(name)
        ws.append([money_head(title) if is_money(src, kind) else tr(title, True)
                   for src, title, _, kind in spec])
        style_header(ws, len(spec))
        for i in range(m["n"]):
            row = []
            for src, _, _, kind in spec:
                v = resolve_value(m, extra, src, i)
                if kind in ("int", "op"):
                    row.append(int(v))
                elif not np.isfinite(float(v)):
                    row.append(None)
                elif is_money(src, kind):
                    row.append(round(float(v) * mscale,
                                     4 if kind in ("f4", "raw4") else 2))
                else:
                    row.append(round(float(v), 4 if kind in ("f4", "raw4") else 2))
            ws.append(row)
        ws.freeze_panes = "C2"
        for c in range(1, len(spec) + 1):
            ws.cell(row=1, column=c).alignment = Alignment(
                horizontal="center", wrap_text=True, vertical="center")
        for idx, (_, _, width, _) in enumerate(spec, start=1):
            ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = \
                max(9, width / 8)
        finish(ws, header_row=1, first_data=2)

    # ── 决策 / LCOE / WACC ────────────────────────────────────────────
    specials = [
        ("术语表", build_glossary()),
        ("决策信息模版", build_decision(
            m, money_scale=mscale, money_unit=("k" if conv else None))),
        ("LCOE计算表", build_lcoe(
            m, money_scale=mscale, money_unit=("k" if conv else "万元"))),
        ("WACC计算表", build_wacc_pack(m, live)),
    ]
    for sheet_name, spec in specials:
        if sheet_name not in wanted:
            continue
        ws = new_sheet(sheet_name)
        if spec.get("type") == "glossary":
            ws.cell(row=1, column=1, value=tr("术语表 Glossary", True)).font = Font(
                bold=True, color="16324F")
            for j, cname in enumerate(spec.get("cols", []), start=1):
                cc = ws.cell(row=3, column=j, value=tr(cname, True))
                cc.fill = head_fill
                cc.font = head_font
                cc.alignment = Alignment(horizontal="center", vertical="center")
            r = 4
            for row in spec.get("rows", []):
                for j, val in enumerate(row, start=1):
                    c2 = ws.cell(row=r, column=j, value=str(val))
                    c2.alignment = Alignment(vertical="top", wrap_text=True)
                r += 1
            from openpyxl.utils import get_column_letter
            for idx, w in enumerate([16, 44, 20, 60], start=1):
                ws.column_dimensions[get_column_letter(idx)].width = w
            finish(ws, header_row=3, first_data=4)
            continue
        if spec.get("type") == "combo":
            r = 1
            for sec in spec["sections"]:
                c = ws.cell(row=r, column=1, value=tr(sec["title"], True))
                c.font = Font(bold=True, color="16324F")
                c.fill = PatternFill("solid", start_color="E8EEF5")
                ws.merge_cells(start_row=r, start_column=1,
                               end_row=r, end_column=max(4, len(sec.get("cols", []))))
                r += 2
                if sec.get("blocks"):
                    for block in sec["blocks"]:
                        for row in block:
                            col = 1
                            for cell in row["cells"]:
                                span = int(cell.get("span", 1))
                                cc = ws.cell(row=r, column=col, value=tr(cell.get("t", "")))
                                if span > 1:
                                    ws.merge_cells(start_row=r, start_column=col,
                                                   end_row=r, end_column=col + span - 1)
                                if cell.get("strong"):
                                    cc.font = Font(bold=True, color="16324F")
                                col += span
                            r += 1
                        r += 1
                elif sec.get("rows") is not None:
                    for j, cname in enumerate(sec.get("cols", []), start=1):
                        cc = ws.cell(row=r, column=j, value=tr(cname, True))
                        cc.fill = head_fill
                        cc.font = head_font
                        cc.alignment = Alignment(horizontal="center", wrap_text=True,
                                                 vertical="center")
                    r += 1
                    for row in sec["rows"]:
                        if "section" in row:
                            ws.cell(row=r, column=1, value=tr(row["section"])).font = sect_font
                        else:
                            for j, val in enumerate(row.get("cells", []), start=1):
                                ws.cell(row=r, column=j, value=tr(val))
                        r += 1
                    if sec.get("footer"):
                        ws.cell(row=r, column=1, value=tr(sec["footer"])).font = Font(
                            italic=True, color="6B7C8F")
                        r += 1
                r += 1
            from openpyxl.utils import get_column_letter
            for idx, w in enumerate([6, 30, 14, 12, 16, 10, 16], start=1):
                ws.column_dimensions[get_column_letter(idx)].width = w
            finish(ws)
            continue
        if spec.get("blocks"):
            r = 1
            for block in spec["blocks"]:
                for row in block:
                    col = 1
                    cls = row.get("cls", "")
                    for cell in row["cells"]:
                        span = int(cell.get("span", 1))
                        c = ws.cell(row=r, column=col, value=tr(cell.get("t", "")))
                        if span > 1:
                            ws.merge_cells(start_row=r, start_column=col,
                                           end_row=r, end_column=col + span - 1)
                        if cell.get("align"):
                            c.alignment = Alignment(horizontal=cell["align"],
                                                    vertical="center",
                                                    wrap_text=True)
                        else:
                            c.alignment = Alignment(vertical="center",
                                                    wrap_text=True)
                        if cell.get("strong"):
                            c.font = Font(bold=True, color="16324F")
                        if cls in ("banner",):
                            c.font = banner_font
                            c.fill = banner_fill
                        elif cls == "sect":
                            c.fill = sect_fill
                            c.font = sect_font
                        elif cls in ("subhead", "balance", "subtotal"):
                            c.fill = PatternFill("solid", start_color="F0F4F8")
                        col += span
                    r += 1
                r += 1
            ws.freeze_panes = "A1"
            from openpyxl.utils import get_column_letter
            for idx, w in enumerate([6, 30, 14, 12, 16, 10, 16, 20], start=1):
                ws.column_dimensions[get_column_letter(idx)].width = w
            finish(ws)
            continue
        ws.append([tr(c, True) for c in spec["cols"]])
        style_header(ws, len(spec["cols"]))
        for row in spec["rows"]:
            if "section" in row:
                ws.append([tr(row["section"])])
                r = ws.max_row
                ws.merge_cells(start_row=r, start_column=1,
                               end_row=r, end_column=len(spec["cols"]))
                for c in range(1, len(spec["cols"]) + 1):
                    cell = ws.cell(row=r, column=c)
                    cell.fill = sect_fill
                    cell.font = sect_font
            else:
                ws.append([tr(v) for v in row["cells"]])
        if spec.get("footer"):
            ws.append([])
            ws.append([tr(spec["footer"])])
            ws.cell(row=ws.max_row, column=1).font = Font(italic=True, color="6B7C8F")
        ws.freeze_panes = "A2"
        widths = [30, 18, 10, 52]
        for idx in range(1, len(spec["cols"]) + 1):
            ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = \
                widths[idx - 1] if idx <= len(widths) else 14
        finish(ws)

    # 去掉未使用的默认空表
    if wb.active.title == "Sheet" and wb.active.max_row == 1 and wb.active.max_column == 1:
        wb.remove(wb.active)

    # 导出件只落静态文本/数值；"="/公式单元格改为全角等号
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                v = cell.value
                if cell.data_type == "f" or (isinstance(v, str) and v.startswith("=")):
                    cell.value = "＝" + str(v).lstrip("=")

    wb.save(path)
