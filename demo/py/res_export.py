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


_KEYS_SORTED = {}


def _sorted_keys(code):
    """词典键按长度倒序（用于含数字的动态句逐段匹配）。"""
    if code not in _KEYS_SORTED:
        t = _i18n_table(code)
        _KEYS_SORTED[code] = sorted((k for k in t if 2 <= len(k) <= 14), key=len, reverse=True)
    return _KEYS_SORTED[code]


def _piecewise(code, s):
    """整串查不到时：按「完整中文片段」译，片段本身在词典里才替换，避免拼出半中半外的混合词。"""
    d = _i18n_table(code)
    if not d:
        return s
    out, i = [], 0
    for m in re.finditer(r"[一-鿿]+", s):
        out.append(s[i:m.start()])
        run = m.group(0)
        out.append(d.get(run) or run)
        i = m.end()
    out.append(s[i:])
    return "".join(out)


def _piecewise_en(s):
    """英文无整串译名时：按完整中文片段查 EN 表 / _EN_EXTRA。"""
    out, i = [], 0
    for m in re.finditer(r"[一-鿿]+", s):
        out.append(s[i:m.start()])
        run = m.group(0)
        out.append(en(run) or _EN_EXTRA.get(run) or run)
        i = m.end()
    out.append(s[i:])
    return "".join(out)


_ENTITY = (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'"))


def _unesc(s):
    """词典里残留的 HTML 实体（如 &amp;）在 Excel 里应还原为原字符。"""
    for a, b in _ENTITY:
        if a in s:
            s = s.replace(a, b)
    return s


def _text_in(code, s):
    """把中文串翻成指定语言代码；无译文回落英文、再回落中文；动态句按完整中文片段译。"""
    out = _unesc(_text_in_raw(code, s))
    if code not in ("", "zh", "zh-CN", "zh-TW") and isinstance(out, str):
        out = out.replace("元/", "CNY/")      # 非中文：单价符号 元/W → CNY/W
    return out


def _text_in_raw(code, s):
    if code in ("", "zh", "zh-CN"):
        return s
    if code == "zh-TW":
        return _i18n_table(code).get(s) or (_to_tw(s) if en(s) in (None, s) else en(s))
    t = _i18n_table(code).get(s)
    if t:
        return t
    e = en(s) or _EN_EXTRA.get(s)
    if e and e != s:
        return e
    if any("一" <= c <= "鿿" for c in s):
        return (_piecewise_en(s) if code == "en" else _piecewise(code, s)) or s
    return s
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

# 动态句中的中文片段（导出时逐段翻译用的英文对照）
_EN_RUNS = {
    '三币种共用': 'Shared across three currencies',
    '不含税': 'Tax-exclusive',
    '为当前口径': 'Current basis',
    '交流': 'AC',
    '信用利差加成': 'Credit spread add-on',
    '债务成本': 'Cost of debt',
    '储能动态投资造价': 'Energy storage dynamic investment cost',
    '储能比例': 'Storage ratio',
    '光伏发电项目': 'PV power generation project',
    '其中': 'Of which',
    '减项': 'Deduction',
    '前期开发阶段': 'Early development stage',
    '前沿': 'Frontier',
    '单价按': 'Unit price based on',
    '取各币种': 'For each currency',
    '取数': 'Data extraction',
    '合成评级法': 'Synthetic rating method',
    '吉尔吉斯斯坦共和国': 'Kyrgyz Republic',
    '含储能': 'Including storage',
    '国债': 'Government bond',
    '国别类别': 'Country category',
    '国别风险溢价': 'Country risk premium',
    '已作为模型折现率': 'Used as model discount rate',
    '年期国债': 'Year government bond',
    '年租金标准': 'Annual rent standard',
    '建设期利息和业主管理费': "Interest during construction and owner's management fee",
    '当收益率为': 'When yield is',
    '总包工程部分': 'EPC portion',
    '总投资为': 'Total investment is',
    '所选币种': 'Selected currency',
    '抓取': 'Extract',
    '投资构成情况': 'Investment composition',
    '折旧与摊销': 'Depreciation and amortization',
    '折现': 'Discounting',
    '折现基准': 'Discount basis',
    '抵税': 'Tax shield',
    '按第': 'Pursuant to Article',
    '数据日期': 'Data date',
    '无杠杆': 'Unlevered',
    '本地快照': 'Local snapshot',
    '权益占比': 'Equity ratio',
    '权益成本': 'Cost of equity',
    '杠杆': 'Leverage',
    '残值': 'Residual value',
    '测算总投资': 'Estimated total investment',
    '电站动态投资造价': 'Power plant dynamic investment cost',
    '直流容量': 'DC capacity',
    '结余': 'Balance',
    '股权风险溢价': 'Equity risk premium',
    '运营第一年': 'First year of operation',
    '造价': 'Cost',
    '配置小时数': 'Configured hours',
    '采用币种': 'Currency used',
    '金额': 'Amount',
    '项目测算情况': 'Project calculation',
    '项结余反推': 'Back-calculate from item balance',
    '首年利用小时': 'First-year utilization hours',
}
_EN_EXTRA.update(_EN_RUNS)

# 英文补充译名（2026-10-26 第二批：列名、单位、动态句片段）
_EN_RUNS_2 = {
    '%（按发电收入）': '% (of generation revenue)',
    'AC/直流容量（MW）容配比\nAC/DC capacity ratio': 'AC/DC capacity ratio (MW)',
    'Average O&M Cost\nAvg O&amp;M Cost\n（元/kW）': 'Average O&M Cost\nAvg O&M Cost\n(CNY/kW)',
    'DSCR 偿债备付率\n（min/avg）': 'DSCR (min/avg)',
    'Depreciation and amortization × Income Tax Rate，折现（减项）\nDepreciation & amortization × tax rate, discounted (deduct)': 'Depreciation & amortization × tax rate, discounted (deduct)',
    'Energy storage dynamic investment cost\nStorage Cost\n（元/Wh）': 'Energy storage dynamic investment cost\nStorage Cost\n(CNY/Wh)',
    'English 英语 (en)': 'English (en)',
    'Land Area\nLand\n（公顷 Hectare）': 'Land Area\nLand\n(hectare)',
    'Of which：储能总投资（k）\nStorage Investment (k)': 'Of which: Storage Investment (k)',
    'Of which：电站总投资（k）\nStation Investment (k)': 'Of which: Station Investment (k)',
    'Power plant dynamic investment cost\nStation Cost\n（元/W）': 'Power plant dynamic investment cost\nStation Cost\n(CNY/W)',
    'Unit：人民币 k · Unit price based on 元/W（储能 元/Wh）计\nUnit: k CNY · Prices in CNY/W (storage CNY/Wh)': 'Unit: k CNY · Prices in CNY/W (storage CNY/Wh)',
    'WACC 三币种对比': 'WACC three-currency comparison',
    'WACC 敏感度': 'WACC sensitivity',
    'WACC 计算过程': 'WACC calculation process',
    'k/人·yr': 'k/person·yr',
    '业主管理费（含电站+储能）Owner mgmt fee (Station+Storage)': 'Owner mgmt fee (Station+Storage)',
    '人民币 RMB（本模型）': 'RMB (this model)',
    '亿kWh': '100 mn kWh',
    '信用利差': 'Credit spread',
    '储能等效小时 (k)': 'Storage equivalent hours (k)',
    '储能系统和工程 Energy Storage Systems & Engineering': 'Energy Storage Systems & Engineering',
    '全投资 IRR\nProject IRR': 'Project IRR',
    '内容 Content': 'Content',
    '单价 Price (元/W · 元/Wh)': 'Price (CNY/W · CNY/Wh)',
    '口径': 'Basis',
    '吉尔吉斯斯坦索姆 KGS（本国货币）': 'Kyrgyzstani som KGS (local currency)',
    '国别违约利差': 'Country default spread',
    '土地补偿（k/年）\nLand Compensation (k/yr)': 'Land Compensation (k/yr)',
    '增值税净额 (k)': 'Net VAT (k)',
    '备注 Note': 'Note',
    '小计 Subtotal': 'Subtotal',
    '小计 Subtotal — Total Investment Total Investment': 'Subtotal — Total Investment',
    '引用左侧「Pre-development Cost」Parameters，如需修改请到参数列表 Referenced from the left-hand parameter list': 'Referenced from the left-hand parameter list (Pre-development Cost Parameters); edit in the parameter list if needed',
    '成熟市场 ERP': 'Mature market ERP',
    '所属行业': 'Industry',
    '本模型未单列 Not modeled': 'Not modeled',
    '汇流箱/箱变 Combiner Box / Transformer': 'Combiner Box / Transformer',
    '电价（不含税）\nElectricity Price\n（元/kWh）': 'Electricity Price (excl. tax, RMB/kWh)',
    '电站上网电量(万kWh) (k)': 'Plant On-grid Electricity (10,000 kWh) (k)',
    '电站等效小时 (k)': 'Plant Equivalent Hours (k)',
    '电芯更换投资 (k)': 'Battery Cell Replacement Investment (k)',
    '编号': 'No.',
    '美元 USD（对照）': 'USD (for reference)',
    '融资费 Financing fee': 'Financing fee',
    '行业无杠杆贝塔取数口径': 'Industry Unlevered Beta Basis',
    '资本金 IRR\nEquity IRR': 'Equity IRR',
    '金额（k）\nAmount (k)': 'Amount (k)',
    '项目总投资（k）\nTotal Investment (k)': 'Total Investment (k)',
    '与': 'and',
    '人民币': 'RMB',
    '元': 'RMB',
    '列': 'Column',
    '吉尔吉斯斯坦': 'Kyrgyzstan',
    '档': 'Tier',
    '行': 'Row',
}
_EN_EXTRA.update(_EN_RUNS_2)

# 英文补充译名（第三批：片段、列名、术语表）
_EN_RUNS_3 = {
    'DSCR 的分子': 'DSCR numerator',
    'EBIT ÷ 利息支出': 'EBIT ÷ interest expense',
    'EBITDA − 折旧 − 摊销': 'EBITDA − depreciation − amortization',
    'k/人·年': 'k/person-year',
    '万': '10k',
    '上网电量按 (1−线损率) 折算': 'Grid-connected electricity converted by (1 − line loss rate)',
    '中文': 'Chinese',
    '交流/直流容量（MW）容配比\nAC/DC capacity ratio': 'AC/DC capacity ratio (MW)',
    '交流侧': 'AC side',
    '人': 'person',
    '人工、维修、材料、保险、土地等年度支出': 'Annual expenditures on labor, maintenance, materials, insurance, land, etc.',
    '企业所得税': 'Corporate income tax',
    '企业自由现金流': 'Free cash flow to firm (FCFF)',
    '使项目净现值为零的折现率；全投资 IRR 不考虑融资结构': 'Discount rate that makes project NPV zero; all-investment IRR ignores financing structure',
    '偿债准备金账户': 'Debt service reserve account (DSRA)',
    '偿债备付率': 'Debt service coverage ratio (DSCR)',
    '储能效率': 'Energy storage efficiency',
    '储能每年的等效满充满放次数': 'Annual equivalent full charge/discharge cycles of energy storage',
    '储能等效小时': 'Storage equivalent hours',
    '充放电全过程效率': 'Round-trip efficiency',
    '光伏组件在标准测试条件下的峰值功率，直流侧计量': 'PV module peak power under STC, measured on DC side',
    '免税期': 'Tax holiday',
    '全投资口径现金流（不扣融资）': 'All-investment cash flow (before financing)',
    '全生命周期成本现值 ÷ 发电量现值，元/kWh': 'Present value of lifecycle costs ÷ present value of electricity generation, RMB/kWh',
    '内部收益率': 'Internal rate of return (IRR)',
    '净现值': 'Net Present Value (NPV)',
    '利息保障倍数': 'Interest Coverage Ratio',
    '加权平均资本成本': 'Weighted Average Cost of Capital (WACC)',
    '千瓦峰 / 兆瓦峰': 'kWp / MWp',
    '单位：人民币 k · 单价按 元/W（储能 元/Wh）计\nUnit: k CNY · Prices in CNY/W (storage CNY/Wh)': 'Unit: k CNY · Prices in CNY/W (storage CNY/Wh)',
    '可用于偿债的现金流': 'Cash Flow Available for Debt Service (CFADS)',
    '可用于还本付息的现金 ÷ 当期还本付息额': 'Cash available for debt service ÷ Current debt service',
    '含自维/外委两种方式': 'Includes self-maintenance and outsourced maintenance',
    '商业运行日': 'Commercial Operation Date (COD)',
    '增值税': 'Value Added Tax (VAT)',
    '增值税净额': 'Net VAT',
    '如需修改请到参数列表': 'To modify, go to the parameter list',
    '容配比': 'DC/AC ratio',
    '小计': 'Subtotal',
    '小计 Subtotal — 项目总投资 Total Investment': 'Subtotal — Total Investment',
    '峰瓦': 'Watt-peak (Wp)',
    '差价补贴': 'Price difference subsidy',
    '平准化度电成本': 'Levelized Cost of Energy (LCOE)',
    '年充放天数': 'Annual charge/discharge days',
    '年衰减率': 'Annual degradation rate',
    '并网点容量口径': 'Grid connection point capacity basis',
    '建设投资': 'Construction investment',
    '建设期借款利息，计入总投资': 'Interest during construction, included in total investment',
    '建设期利息': 'Interest during construction',
    '引用左侧': 'Reference left side',
    '引用左侧「项目前期开发费」参数，如需修改请到参数列表 Referenced from the left-hand parameter list': "References the left-hand 'Project Pre-development Fee' parameter; to modify, go to the parameter list",
    '息税前利润': 'EBIT',
    '息税折旧摊销前利润': 'EBITDA',
    '扣除还本付息后的股东现金流': 'Equity cash flow after debt service',
    '按 WACC 折现的现金流现值之和；>0 表示超过基准回报': 'Sum of discounted cash flows at WACC; >0 indicates above benchmark return',
    '按股东实际现金流出/流入计算的收益率': 'Return based on actual shareholder cash outflows/inflows',
    '按还本付息额留存的储备金': 'Debt service reserve',
    '期末固定资产余值折现': 'Discounted terminal fixed asset salvage value',
    '期末固定资产余值折现（减项）\nTerminal salvage value, discounted (deduct)': 'Terminal salvage value, discounted (deduction)',
    '本模型中电站与储能各自一个 EPC 总价': 'In this model, the power plant and energy storage each have one EPC lump-sum price',
    '本模型按税率与免税年限计算': 'This model calculates based on tax rate and tax exemption period',
    '本项目以投产年表示': 'This project is expressed by commissioning year',
    '术语': 'Terminology',
    '术语表': 'Glossary',
    '术语表 Glossary': 'Glossary',
    '瓦时 / 千瓦时 / 兆瓦时': 'Wh / kWh / MWh',
    '电站 + 储能的 EPC 及管理费': 'EPC and management fees for power plant + energy storage',
    '电站上网电量': 'Plant on-grid electricity',
    '电站上网电量(万kWh)': 'Plant on-grid electricity (10,000 kWh)',
    '电站等效小时': 'Plant equivalent full-load hours',
    '电芯更换投资': 'Battery cell replacement investment',
    '电量单位；储能容量与造价按 Wh 计': 'Energy unit; storage capacity and cost are based on Wh',
    '直接免税 N 年，或三免三减半': 'Direct tax exemption for N years, or 3 years exempt + 3 years half-rate',
    '直流侧': 'DC side',
    '直流装机 ÷ 交流装机': 'DC capacity ÷ AC capacity',
    '约定电价与电量的长期售电合同': 'Long-term power sales contract with agreed tariff and volume',
    '线损率': 'Line loss rate',
    '组件容量口径，本模型发电量按 DC 容量计': 'Module capacity basis; generation in this model is calculated based on DC capacity',
    '组件效率逐年下降，本模型按首年折减 + 年衰减': 'Module efficiency declines annually; this model applies first-year derating + annual degradation',
    '经营性现金的近似口径': 'Approximate operating cash flow basis',
    '经营成本': 'Operating costs',
    '缩写': 'Abbreviation',
    '缩写 / 术语': 'Abbreviation / Term',
    '股债加权折现率，本项目按 CAPM 合成': 'Weighted average cost of capital (WACC), derived via CAPM for this project',
    '股权自由现金流': 'Free cash flow to equity (FCFE)',
    '英文全称': 'Full English name',
    '补贴年限内叠加的度电补贴': 'Per-kWh subsidy stacked within the subsidy period',
    '计': 'Calculate',
    '设计采购施工总承包': 'Engineering, procurement, and construction (EPC) turnkey contracting',
    '购电协议': 'Power purchase agreement (PPA)',
    '资本金 IRR': 'Equity IRR',
    '运维': 'O&M',
    '销项 − 进项 − 留抵 = 应交；EPC 含税、可抵扣': 'Output VAT − input VAT − carried-forward VAT credit = VAT payable; EPC is tax-inclusive and deductible',
}
_EN_EXTRA.update(_EN_RUNS_3)


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

    # 「跟随界面语言」导出时的语言序列（副语言为「无」则只剩一个，即单语版）
    pair_codes = [c for c in (langs or []) if c and c != "none"] if lang == "pair" else []
    ZH_CODES = {"zh", "zh-CN", "zh-TW"}

    def pair_unit(u):
        """复合单位（万元/人·年、元/MWh·年）按语言逐个生成，再上下并排。"""
        out = []
        for c in (pair_codes or ["zh"]):
            t = u
            s = _text_in(c, t)
            if s == t and ("/" in t or "·" in t):        # 整串查不到 → 分段译
                head, sep, tail = t.partition("/")
                segs = [head] + [x for x in re.split(r"·", tail) if x]
                s = _text_in(c, segs[0])
                if sep:
                    s += "/" + "·".join(_text_in(c, x) for x in segs[1:])
            if s and s not in out:
                out.append(s)
        return "\n".join(out) if out else u

    # 非中文语言：货币值 ×10（1 万元 = 10 k），单位改用 k
    conv = (lang in ("en", "zh-TW") and lang != "pair") or \
           (lang == "pair" and bool(pair_codes) and pair_codes[0] not in ZH_CODES)
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
                unit_txt = _UNIT_EN.get(unit) or _text_in("en", unit)
            elif lang == "zh-TW":
                unit_txt = _to_tw(unit.replace("万元", "k") if money_conv else unit)
            elif lang == "pair":
                unit_txt = pair_unit(unit.replace("万元", "k") if money_conv else unit)
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
                elif lang == "pair":
                    val = tr(str(lab), True)
                else:
                    val = str(lab)
            elif lang == "en" and isinstance(val, str):
                val = en(val) or _EN_EXTRA.get(val) or val
            elif lang == "pair" and isinstance(val, str):
                val = tr(val, True)
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
                    c2 = ws.cell(row=r, column=j, value=tr(str(val), True))
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
