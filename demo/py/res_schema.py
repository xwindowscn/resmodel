#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RNE 模型：参数表、报表定义与数值格式化（界面与导出共用，无 GUI 依赖）。"""
import numpy as np

import res_wacc_data as WD

# ── 参数定义：全部可填驱动量（派生量由引擎按公式重算，不在表单中）────────
# kind: float | int | pct | choice | text
GROUPS = [
    ("基本情形", [
        ("scenario", "情景预设", "choice", ""),
        ("project_name", "项目名称（中文）", "text", ""),
        ("project_name_en", "项目名称（英文）", "text", ""),
        ("ui_lang", "界面语言（主）", "choice", ""),
        ("ui_lang2", "界面语言（副/对照）", "choice", ""),
        ("display_ccy", "计价货币", "choice", ""),
        ("storage_ratio", "储能配置比例", "pct", "%"),
        ("storage_duration", "储能配置时长", "float", "h"),
        ("gen_type", "发电类型", "choice", ""),
        ("plant_type", "电站类型", "choice", ""),
        ("battery_type", "电池类型", "choice", ""),
        ("start_year", "投产年", "int", "年"),
        ("construct_period", "建设期", "int", "年"),
        ("oper_period", "运营期", "int", "年"),
        ("sea_area_fee", "海域使用金", "float", "万元/年"),
    ]),
    ("装机与发电", [
        ("cap_ac_mw", "交流装机（AC）", "float", "MW"),
        ("cap_dc_mw", "直流装机（DC）", "float", "MW"),
        ("actual_gen_hours", "首年发电小时数", "float", "h/年"),
        ("line_loss", "线损率", "pct", "%"),
        ("market_trade_hours", "市场化交易小时数", "float", "h/年"),
        ("overgen_hours", "超发小时数", "float", "h/年"),
        ("first_year_haircut", "首年折减", "pct", "%"),
        ("annual_degradation", "组件年衰减", "pct", "%/年"),
        ("wc_per_kw", "流动资金", "float", "元/kWp(DC)"),
    ]),
    ("电价", [
        ("benchmark_tariff", "基准电价（PPA）", "float", "元/kWh"),
        ("market_price", "市场化交易电价", "float", "元/kWh"),
        ("overgen_price", "超发电价", "float", "元/kWh"),
        ("storage_elec_price", "储能上网电价", "float", "元/kWh"),
        ("grid_fee", "过网费", "float", "元/kWh"),
        ("ancillary_fee", "辅助服务费", "float", "元/kWh"),
        ("guarantee_discount", "保障电价折让", "pct", "%"),
        ("subsidy_price", "差价补贴单价", "float", "元/kWh"),
        ("subsidy_years", "差价补贴年限", "int", "年"),
        ("tariff_incl_tax", "电价是否含税", "choice", ""),
    ]),
    ("储能", [
        ("storage_days", "年充放天数", "float", "天/年"),
        ("storage_usable_hours", "电芯可用小时", "float", "h"),
        ("storage_lease_price", "租赁价格", "float", "元/kWh"),
        ("storage_unit_price", "储能 EPC 单价", "float", "元/Wh"),
        ("owner_mgmt_rate_stor", "储能建设管理费率", "pct", "%"),
        ("replace_cost", "电芯更换单价", "float", "元/Wh"),
        ("storage_rev_on", "储能上网收入", "choice", ""),
    ]),
    ("储能运维", [
    ("storage_staff_per_100mwh", "储能运维人员", "float", "人/100MWh"),
    ("storage_outsource_per_100mw", "储能外委人员", "float", "人/100MW"),
    ("storage_self_mat_in", "储能自维材料费(质保内)", "float", "元/MWh·年"),
    ("storage_self_mat_out", "储能自维材料费(质保外)", "float", "元/MWh·年"),
    ("storage_self_rep_in", "储能自维维修费(质保内)", "float", "元/MWh·年"),
    ("storage_self_rep_out", "储能自维维修费(质保外)", "float", "元/MWh·年"),
    ("storage_out_mat_in", "储能外委材料费(质保内)", "float", "元/MWh·年"),
    ("storage_out_mat_out", "储能外委材料费(质保外)", "float", "元/MWh·年"),
    ("storage_out_rep_in", "储能外委维修费(质保内)", "float", "元/MWh·年"),
    ("storage_out_rep_out", "储能外委维修费(质保外)", "float", "元/MWh·年"),
    ("storage_self_other_in", "储能自维其他费(质保内)", "float", "元/kWp·年"),
    ("storage_self_other_out", "储能自维其他费(质保外)", "float", "元/kWp·年"),
    ("storage_out_other_in", "储能外委其他费(质保内)", "float", "元/kWp·年"),
    ("storage_out_other_out", "储能外委其他费(质保外)", "float", "元/kWp·年"),
    ("storage_opex", "储能其他运维费", "float", "万元/年"),
    ]),
    ("电站投资", [
        ("epc_price_station", "电站 EPC 单价", "float", "元/Wp(DC)"),
        ("owner_mgmt_rate_stn", "电站建设管理费率", "pct", "%"),
        ("predev_price_per_w", "项目前期开发费", "float", "元/Wp"),
        # 单位建设投资已改为派生量（由电站 EPC + 储能 EPC 反算），不再作为输入
    ]),
    ("折旧", [
        ("dep_life", "折旧年限", "int", "年"),
        ("salvage_rate", "残值率", "pct", "%"),
        ("decomm_ratio", "退役拆除费率", "pct", "%（末年末）"),
    ]),
    ("电站运维", [
        ("om_mode", "运维方式", "choice", ""),
        ("cost_method", "成本方法", "choice", ""),
        ("om_cost_mode", "运维成本口径", "choice", ""),
        ("om_cost_pct", "投资额比例法费率", "pct", "%/年"),
        ("warranty_years", "质保年限", "int", "年"),
        ("staff_per_50mw", "自有人员配置", "float", "人/50MW"),
        ("outsource_per_50mw", "外委人员配置", "float", "人/50MW"),
        ("avg_salary", "人均年薪", "float", "万元/人·年"),
        ("benefits_ratio", "福利比例", "pct", "%"),
        ("land_area", "项目占地", "float", "公顷"),
        ("land_rent_usd", "土地租金标准", "float", "美元/公顷·年"),
        ("exchange_rate", "汇率", "float", "元/美元"),
        ("other_cost_rate", "其他费用", "float", "元/kWp"),
        ("land_comp_annual", "土地补偿", "float", "万元/年"),
        ("land_compensation", "征地补偿标准", "float", "美元/公顷·年"),
        ("land_tax", "土地使用税", "float", "万元/年"),
        ("land_tax_base", "土地税计税基础", "float", "元/平方米"),
        ("land_tax_rate", "土地税率", "pct", "%"),
        ("property_tax_rate", "房产税率", "pct", "%"),        ("cpi", "成本年涨幅", "pct", "%/年"),
        ("om_self_mat_in", "自维材料费(质保内)", "float", "元/kWp"),
        ("om_self_mat_out", "自维材料费(质保外)", "float", "元/kWp"),
        ("om_self_rep_in", "自维维修费(质保内)", "float", "元/kWp"),
        ("om_self_rep_out", "自维维修费(质保外)", "float", "元/kWp"),
        ("om_out_mat_in", "外委材料费(质保内)", "float", "元/kWp"),
        ("om_out_mat_out", "外委材料费(质保外)", "float", "元/kWp"),
        ("om_out_rep_in", "外委维修费(质保内)", "float", "元/kWp"),
        ("om_out_rep_out", "外委维修费(质保外)", "float", "元/kWp"),
        ("om_self_other_in", "自维其他费(质保内)", "float", "元/kWp"),
        ("om_self_other_out", "自维其他费(质保外)", "float", "元/kWp"),
        ("om_out_other_in", "外委其他费(质保内)", "float", "元/kWp"),
        ("om_out_other_out", "外委其他费(质保外)", "float", "元/kWp"),
        ("self_rep_rate_in", "自维维修费率(质保内)", "pct", "%"),
        ("self_rep_rate_out", "自维维修费率(质保外)", "pct", "%"),
        ("out_rep_rate_in", "外委维修费率(质保内)", "pct", "%"),
        ("out_rep_rate_out", "外委维修费率(质保外)", "pct", "%"),
        ("om_out_annual", "外委固定年费", "float", "万元/年"),
        ("insurance_method", "保险费方式", "choice", ""),
        ("insurance_rate", "保险费率(首档)", "pct", "%"),
        ("ins_rate2", "保险费率(第2档)", "pct", "%"),
        ("ins_rate3", "保险费率(第3档)", "pct", "%"),
        ("ins_rate4", "保险费率(第4档)", "pct", "%"),
        ("ins_rate5", "保险费率(第5档)", "pct", "%"),
        ("insurance_fixed_rate", "保险固定费率", "pct", "%"),
    ]),
    ("融资", [
        ("debt_ratio", "债务占比", "pct", "%"),
        ("debt_rate", "债务利率", "pct", "%"),
        ("debt_tenor", "借款期限", "int", "年"),
        ("repay_method", "还本方式", "choice", ""),
        ("dsra_months", "DSRA 月数", "float", "月"),
        ("wc_loan_rate", "流贷利率", "pct", "%"),
        ("wc_loan_ratio", "流贷占比", "pct", "%"),
        ("debt_base_mode", "债务基数口径", "choice", ""),
    ]),
    ("税务", [
        ("tax_rate", "所得税率", "pct", "%"),
        ("tax_holiday_mode", "免税方式", "choice", ""),
        ("tax_preference_years", "优惠税率年限", "int", "年"),
        ("withholding_rate", "预扣税率", "pct", "%"),
        ("reserve_rate", "盈余公积比例", "pct", "%"),
        ("vat_rate", "增值税率", "pct", "%"),
        ("vat_exempt_years", "增值税免税年限", "int", "年"),
        ("sales_tax_rate", "销售税率", "pct", "%"),
        ("local_levy_mode", "其他特别费用方式", "choice", ""),
        ("local_levy_rate", "其他特别费用比例", "pct", "%（按发电收入）"),
        ("local_levy_amount", "其他特别费用金额", "float", "万元/年"),
        ("sales_tax_exempt_years", "销售税免税年限", "int", "年"),
        ("city_constr_tax", "城建税率", "pct", "%"),
        ("edu_surcharge", "教育附加率", "pct", "%"),
        ("vat_refund", "增值税返还", "choice", ""),
    ]),
    ("折现与风险 (WACC)", [
        ("wacc_country", "项目所在国", "choice", ""),
        ("wacc_sector", "所属行业（取 βu）", "choice", ""),
        ("wacc_ccy", "WACC 采用币种", "choice", ""),
        ("rd_method", "Rd 确定方式", "choice", ""),
        ("wacc_rd", "投资人指定 Rd", "pct", "%"),
    ]),
]


# ── 计价货币 ─────────────────────────────────────────────────────────
# (选择项, 代码, 中文单位, 英文单位, 单价前缀)
UI_LANGS = [
    ("中文 (zh)", "zh"),
    ("繁體中文 (zh-TW)", "zh-TW"),
    ("English 英语 (en)", "en"),
    ("Русский 俄语 (ru)", "ru"),
    ("Español 西班牙语 (es)", "es"),
    ("日本語 日语 (ja)", "ja"),
    ("ไทย 泰语 (th)", "th"),
    ("Bahasa Indonesia 印尼语 (id)", "id"),
    ("Tiếng Việt 越南语 (vi)", "vi"),
    ("ខ្មែរ 高棉语 (km)", "km"),
    ("မြန်မာ 缅甸语 (my)", "my"),
    ("ລາວ 老挝语 (lo)", "lo"),
    ("Қазақша 哈萨克语 (kk)", "kk"),
    ("Кыргызча 吉尔吉斯语 (ky)", "ky"),
    ("Oʻzbekcha 乌兹别克语 (uz)", "uz"),
    ("Тоҷикӣ 塔吉克语 (tg)", "tg"),
    ("العربية 阿拉伯语 (ar)", "ar"),
]

UI_LANG2 = [("无（单语言）", "none")] + UI_LANGS

CCY_LIST = [
    ("人民币 CNY", "CNY", "万元", "10K CNY", "元"),
    ("港币 HKD", "HKD", "万港元", "10K HKD", "港元"),
    ("新台币 TWD", "TWD", "万新台币", "10K TWD", "新台币"),
    ("澳门元 MOP", "MOP", "万澳门元", "10K MOP", "澳门元"),
    ("日元 JPY", "JPY", "万日元", "10K JPY", "日元"),
    ("韩元 KRW", "KRW", "万韩元", "10K KRW", "韩元"),
    ("图格里克 MNT", "MNT", "万图格里克", "10K MNT", "图格里克"),
    ("新加坡元 SGD", "SGD", "万新元", "10K SGD", "新元"),
    ("马来西亚林吉特 MYR", "MYR", "万林吉特", "10K MYR", "林吉特"),
    ("泰铢 THB", "THB", "万泰铢", "10K THB", "泰铢"),
    ("印尼盾 IDR", "IDR", "万印尼盾", "10K IDR", "印尼盾"),
    ("菲律宾比索 PHP", "PHP", "万比索", "10K PHP", "比索"),
    ("越南盾 VND", "VND", "万越南盾", "10K VND", "越南盾"),
    ("缅元 MMK", "MMK", "万缅元", "10K MMK", "缅元"),
    ("柬埔寨瑞尔 KHR", "KHR", "万瑞尔", "10K KHR", "瑞尔"),
    ("老挝基普 LAK", "LAK", "万基普", "10K LAK", "基普"),
    ("文莱元 BND", "BND", "万文莱元", "10K BND", "文莱元"),
    ("哈萨克斯坦坚戈 KZT", "KZT", "万坚戈", "10K KZT", "坚戈"),
    ("吉尔吉斯斯坦索姆 KGS", "KGS", "万索姆", "10K KGS", "索姆"),
    ("乌兹别克斯坦苏姆 UZS", "UZS", "万苏姆", "10K UZS", "苏姆"),
    ("塔吉克斯坦索莫尼 TJS", "TJS", "万索莫尼", "10K TJS", "索莫尼"),
    ("土库曼斯坦马纳特 TMT", "TMT", "万马纳特", "10K TMT", "马纳特"),
    ("印度卢比 INR", "INR", "万印度卢比", "10K INR", "印度卢比"),
    ("巴基斯坦卢比 PKR", "PKR", "万巴基斯坦卢比", "10K PKR", "巴基斯坦卢比"),
    ("孟加拉塔卡 BDT", "BDT", "万塔卡", "10K BDT", "塔卡"),
    ("斯里兰卡卢比 LKR", "LKR", "万斯里兰卡卢比", "10K LKR", "斯里兰卡卢比"),
    ("尼泊尔卢比 NPR", "NPR", "万尼泊尔卢比", "10K NPR", "尼泊尔卢比"),
    ("阿联酋迪拉姆 AED", "AED", "万迪拉姆", "10K AED", "迪拉姆"),
    ("沙特里亚尔 SAR", "SAR", "万里亚尔", "10K SAR", "里亚尔"),
    ("卡塔尔里亚尔 QAR", "QAR", "万里亚尔", "10K QAR", "里亚尔"),
    ("科威特第纳尔 KWD", "KWD", "万第纳尔", "10K KWD", "第纳尔"),
    ("巴林第纳尔 BHD", "BHD", "万第纳尔", "10K BHD", "第纳尔"),
    ("阿曼里亚尔 OMR", "OMR", "万里亚尔", "10K OMR", "里亚尔"),
    ("以色列谢克尔 ILS", "ILS", "万谢克尔", "10K ILS", "谢克尔"),
    ("土耳其里拉 TRY", "TRY", "万里拉", "10K TRY", "里拉"),
    ("伊朗里亚尔 IRR", "IRR", "万里亚尔", "10K IRR", "里亚尔"),
    ("伊拉克第纳尔 IQD", "IQD", "万第纳尔", "10K IQD", "第纳尔"),
    ("约旦第纳尔 JOD", "JOD", "万第纳尔", "10K JOD", "第纳尔"),
    ("黎巴嫩镑 LBP", "LBP", "万黎巴嫩镑", "10K LBP", "黎巴嫩镑"),
    ("欧元 EUR", "EUR", "万欧元", "10K EUR", "欧元"),
    ("英镑 GBP", "GBP", "万英镑", "10K GBP", "英镑"),
    ("瑞士法郎 CHF", "CHF", "万瑞士法郎", "10K CHF", "瑞士法郎"),
    ("俄罗斯卢布 RUB", "RUB", "万卢布", "10K RUB", "卢布"),
    ("乌克兰格里夫纳 UAH", "UAH", "万格里夫纳", "10K UAH", "格里夫纳"),
    ("波兰兹罗提 PLN", "PLN", "万兹罗提", "10K PLN", "兹罗提"),
    ("捷克克朗 CZK", "CZK", "万捷克克朗", "10K CZK", "捷克克朗"),
    ("匈牙利福林 HUF", "HUF", "万福林", "10K HUF", "福林"),
    ("罗马尼亚列伊 RON", "RON", "万列伊", "10K RON", "列伊"),
    ("保加利亚列弗 BGN", "BGN", "万列弗", "10K BGN", "列弗"),
    ("塞尔维亚第纳尔 RSD", "RSD", "万第纳尔", "10K RSD", "第纳尔"),
    ("瑞典克朗 SEK", "SEK", "万瑞典克朗", "10K SEK", "瑞典克朗"),
    ("挪威克朗 NOK", "NOK", "万挪威克朗", "10K NOK", "挪威克朗"),
    ("丹麦克朗 DKK", "DKK", "万丹麦克朗", "10K DKK", "丹麦克朗"),
    ("冰岛克朗 ISK", "ISK", "万冰岛克朗", "10K ISK", "冰岛克朗"),
    ("美元 USD", "USD", "万美元", "10K USD", "美元"),
    ("加拿大元 CAD", "CAD", "万加元", "10K CAD", "加元"),
    ("墨西哥比索 MXN", "MXN", "万墨西哥比索", "10K MXN", "墨西哥比索"),
    ("巴西雷亚尔 BRL", "BRL", "万雷亚尔", "10K BRL", "雷亚尔"),
    ("阿根廷比索 ARS", "ARS", "万阿根廷比索", "10K ARS", "阿根廷比索"),
    ("智利比索 CLP", "CLP", "万智利比索", "10K CLP", "智利比索"),
    ("哥伦比亚比索 COP", "COP", "万哥伦比亚比索", "10K COP", "哥伦比亚比索"),
    ("秘鲁索尔 PEN", "PEN", "万索尔", "10K PEN", "索尔"),
    ("乌拉圭比索 UYU", "UYU", "万乌拉圭比索", "10K UYU", "乌拉圭比索"),
    ("澳元 AUD", "AUD", "万澳元", "10K AUD", "澳元"),
    ("新西兰元 NZD", "NZD", "万新西兰元", "10K NZD", "新西兰元"),
    ("斐济元 FJD", "FJD", "万斐济元", "10K FJD", "斐济元"),
    ("巴布亚新几内亚基那 PGK", "PGK", "万基那", "10K PGK", "基那"),
    ("南非兰特 ZAR", "ZAR", "万兰特", "10K ZAR", "兰特"),
    ("埃及镑 EGP", "EGP", "万埃及镑", "10K EGP", "埃及镑"),
    ("尼日利亚奈拉 NGN", "NGN", "万奈拉", "10K NGN", "奈拉"),
    ("肯尼亚先令 KES", "KES", "万肯尼亚先令", "10K KES", "肯尼亚先令"),
    ("摩洛哥迪拉姆 MAD", "MAD", "万迪拉姆", "10K MAD", "迪拉姆"),
    ("坦桑尼亚先令 TZS", "TZS", "万先令", "10K TZS", "先令"),
    ("加纳塞地 GHS", "GHS", "万塞地", "10K GHS", "塞地"),
]
CCY_CODES = [c[1] for c in CCY_LIST]
CCY_MAP = {c[1]: {"cn": c[2], "en": c[3], "prefix": c[4]} for c in CCY_LIST}

CHOICES = {
    "scenario": (["基准", "保守", "乐观"], {"基准": "基准", "保守": "保守", "乐观": "乐观"}),
    "gen_type": (["光伏", "风电"], {"光伏": "pv", "风电": "wind"}),
    "plant_type": (["陆上/光伏储能", "海上"], {"陆上/光伏储能": 1, "海上": 2}),
    "battery_type": (["磷酸铁锂", "三元锂", "液流电池"],
                     {"磷酸铁锂": "磷酸铁锂", "三元锂": "三元锂",
                      "液流电池": "液流电池"}),
    "tariff_incl_tax": (["否", "是"], {"否": 0, "是": 1}),
    "om_mode": (["自维", "外委"], {"自维": 1, "外委": 2}),
    "display_ccy": ([c[0] for c in CCY_LIST], {c[0]: c[1] for c in CCY_LIST}),
    "ui_lang": ([c[0] for c in UI_LANGS], {c[0]: c[1] for c in UI_LANGS}),
    "ui_lang2": ([c[0] for c in UI_LANG2], {c[0]: c[1] for c in UI_LANG2}),
    "cost_method": (["定额", "比例", "仅储能"], {"定额": 1, "比例": 2, "仅储能": 3}),
    "insurance_method": (["固定定额", "自定比率"], {"固定定额": 1, "自定比率": 2}),
    "repay_method": (["等额本息", "等额本金"], {"等额本息": 1, "等额本金": 2}),
    "local_levy_mode": (["按发电收入百分比", "固定金额"], {"按发电收入百分比": 0, "固定金额": 1}),
    "om_cost_mode": (["自下而上分项", "投资额×比例"], {"自下而上分项": 0, "投资额×比例": 1}),
    "storage_rev_on": (["计储能上网收入", "不计（并入电站）"], {"计储能上网收入": 1, "不计（并入电站）": 0}),
    "debt_base_mode": (["折旧基数（可抵押资产）", "项目总投资"], {"折旧基数（可抵押资产）": 0, "项目总投资": 1}),
    "tax_holiday_mode": (["直接免税", "三免三减半"], {"直接免税": 0, "三免三减半": 1}),
    "vat_refund": (["否", "是"], {"否": 0, "是": 1}),
    # WACC 选择项：前端用 fieldOptions 重建为「标签 → 取值」，coerce 直接接受取值
    "wacc_country": (["Kyrgyzstan"], {"Kyrgyzstan": "Kyrgyzstan"}),
    "wacc_sector": (["Green & Renewable Energy"],
                    {"Green & Renewable Energy": "Green & Renewable Energy"}),
    "wacc_ccy": (["人民币 RMB", "美元 USD", "本国货币 Local"],
                 {"人民币 RMB": "CNY", "美元 USD": "USD", "本国货币 Local": "LOCAL"}),
    "rd_method": (["是（合成评级法）", "否（投资人指定）"],
                  {"是（合成评级法）": 1, "否（投资人指定）": 0}),
}

# ── 自适应显示规则：(字段, 驱动字段, 显示时的取值[标签]) ─────────────────
# 生效时「灰化且不可填」，并强制按 0 参与计算（区别于 FIELD_RULES 的隐藏）
FIELD_DISABLE = []   # 生效时灰化且不可填（当前无规则）

FIELD_RULES = [
    ("plant_type", "gen_type", ["风电"]),
    ("sea_area_fee", "plant_type", ["海上"]),
    ("om_out_annual", "om_mode", ["外委"]),
    ("om_cost_pct", "om_cost_mode", ["投资额×比例"]),
    ("local_levy_amount", "local_levy_mode", ["固定金额"]),
    ("local_levy_rate", "local_levy_mode", ["按发电收入百分比"]),
    ("om_self_mat_in", "om_mode", ["自维"]),
    ("om_self_mat_out", "om_mode", ["自维"]),
    ("om_self_rep_in", "om_mode", ["自维"]),
    ("om_self_rep_out", "om_mode", ["自维"]),
    ("om_out_mat_in", "om_mode", ["外委"]),
    ("om_out_mat_out", "om_mode", ["外委"]),
    ("om_out_rep_in", "om_mode", ["外委"]),
    ("om_out_rep_out", "om_mode", ["外委"]),
    ("insurance_rate", "insurance_method", ["自定比率"]),
    ("ins_rate2", "insurance_method", ["自定比率"]),
    ("ins_rate3", "insurance_method", ["自定比率"]),
    ("ins_rate4", "insurance_method", ["自定比率"]),
    ("ins_rate5", "insurance_method", ["自定比率"]),
    ("insurance_fixed_rate", "insurance_method", ["固定定额"]),
    ("self_rep_rate_in", "cost_method", ["比例"]),
    ("self_rep_rate_out", "cost_method", ["比例"]),
    ("out_rep_rate_in", "cost_method", ["比例"]),
    ("out_rep_rate_out", "cost_method", ["比例"]),
    ("om_self_other_in", "om_mode", ["自维"]),
    ("om_self_other_out", "om_mode", ["自维"]),
    ("om_out_other_in", "om_mode", ["外委"]),
    ("om_out_other_out", "om_mode", ["外委"]),
    ("storage_staff_per_100mwh", "om_mode", ["自维"]),
    ("storage_outsource_per_100mw", "om_mode", ["外委"]),
    ("storage_self_mat_in", "om_mode", ["自维"]),
    ("storage_self_mat_out", "om_mode", ["自维"]),
    ("storage_self_rep_in", "om_mode", ["自维"]),
    ("storage_self_rep_out", "om_mode", ["自维"]),
    ("storage_self_other_in", "om_mode", ["自维"]),
    ("storage_self_other_out", "om_mode", ["自维"]),
    ("storage_out_mat_in", "om_mode", ["外委"]),
    ("storage_out_mat_out", "om_mode", ["外委"]),
    ("storage_out_rep_in", "om_mode", ["外委"]),
    ("storage_out_rep_out", "om_mode", ["外委"]),
    ("storage_out_other_in", "om_mode", ["外委"]),
    ("storage_out_other_out", "om_mode", ["外委"]),
    ("tax_preference_years", "tax_holiday_mode", ["直接免税"]),
    ("wacc_rd", "rd_method", ["0", "否（投资人指定）"]),
]

# ── 方法说明（随选项切换，显示在字段下方）────────────────────────────────
# 静态提示（每行输入下方的小字说明，与选项无关）
FIELD_HINTS = {
    "exchange_rate": (
        "美元兑人民币汇率（元/美元）。默认使用联网实时汇率（1 美元 = 实时人民币），"
        "仅在离线且从未取到过实时值时用本参数兜底。",
        "USD/CNY rate. The live rate (1 USD = real-time CNY) is used by default; this value is only a "
        "fallback when offline and no live quote was ever fetched."),
    "storage_ratio": (
        "储能配置比例（相对直流容量）。储能等效小时 = 比例 × 年充放天数 × 储能时长。",
        "Storage ratio vs DC capacity; storage equivalent hours = ratio × cycling days × duration."),
    "storage_duration": (
        "储能配置时长（小时）。同时用于储能 EPC 与租赁收入。",
        "Storage duration in hours; used by storage EPC and lease revenue."),
    "storage_days": (
        "年充放天数（每年等效满充放次数）。",
        "Annual equivalent full cycles (days)."),
    "storage_unit_price": (
        "储能 EPC 单价（元/Wh）。储能 EPC 总价 = 容量 × 比例 × 时长 × 单价（+ 更换折现）。",
        "Storage EPC unit price (CNY/Wh). EPC = capacity × ratio × duration × price (+ PV of replacements)."),
    "line_loss": (
        "线损率：四档小时（保障/市场化/超发/储能）统一按 (1−线损率) 折算。",
        "Line loss: all four hour buckets are scaled by (1 − line loss)."),
    "first_year_haircut": (
        "首年不折减；自第 2 年起每年按此比例折减发电小时数。",
        "No haircut in year 1; from year 2 the generation hours drop by this rate each year."),
    "epc_price_station": (
        "电站 EPC 单价（元/W，直流侧）。电站 EPC 总价 = 直流容量 × 本单价 × 100。",
        "Station EPC unit price (CNY/W, DC). Station EPC = DC capacity × this price × 100."),
    "owner_mgmt_rate_stn": (
        "电站建设管理费率：在电站 EPC 之外另计，计入电站总投资。",
        "Station management fee rate, charged on top of station EPC and included in station total investment."),
    "owner_mgmt_rate_stor": (
        "储能建设管理费率：在储能 EPC 之外另计，计入储能总投资。",
        "Storage management fee rate, charged on top of storage EPC and included in storage total investment."),
    "vat_refund": (
        "【保留位·未使用】当前版本不参与任何计算（引擎从未引用）。"
        "实现口径（留抵退还 50% 还是应交减半）待裁定后再接线。",
        "Reserved, not wired: this switch is not used by any calculation in this build."),
    "vat_rate": (
        "增值税率。EPC 价为含税价，建设期进项税作期初留抵；运营期销项 = 不含税收入 × 税率 × 减免系数。"
        "含税情形下进项税不构成费用，损益按不含税经营成本计。",
        "VAT rate. EPC prices are VAT-inclusive; capex input VAT becomes the opening credit; output VAT = net revenue × rate × relief factor."),
    "vat_exempt_years": (
        "增值税免税年限（「直接免税」模式下生效）；选「三免三减半」时改按前 3 年免、4–6 年减半、第 7 年起全额。",
        "VAT exemption years (direct-exemption mode). With three-free/three-half it becomes: 0 for years 1–3, 50% for 4–6, full from year 7."),
    "tax_holiday_mode": (
        "免税方式：直接免税 N 年，或三免三减半（所得税与增值税同口径）。",
        "Tax holiday mode: direct exemption for N years, or three-free/three-half (applies to income tax and VAT alike)."),
    "city_constr_tax": (
        "城市维护建设税率：附加税 = 应交增值税 ×（城建税率 + 教育费附加率）；默认 0。",
        "City construction tax rate; surcharge = VAT payable × (city + education). Default 0."),
    "edu_surcharge": (
        "教育费附加率：附加税 = 应交增值税 ×（城建税率 + 教育费附加率）；默认 0。",
        "Education surcharge rate; surcharge = VAT payable × (city + education). Default 0."),
    "actual_gen_hours": (
        "首年发电小时数（P50／实测）。储能等效小时、市场化交易小时、超发小时在收入分档时自动扣除，此处无需扣。",
        "First-year generation hours (P50 or measured). Storage, market-trading and excess hours are deducted "
        "automatically when splitting revenue."),
    "market_trade_hours": (
        "参与市场化交易的电量小时数，按「市场化交易电价」结算；默认 0。",
        "Hours settled at the market tariff; default 0."),
    "overgen_hours": (
        "超出保障范围、按「超发电价」结算的小时数；默认 0。",
        "Hours settled at the excess-generation tariff; default 0."),
    "benchmark_tariff": (
        "PPA 电价。保障收购电价（实际上网电价）由它派生 =（PPA − 过网费 − 辅助服务费）×（1 − 保障电价折让）+ 差价补贴（仅补贴年限内）。",
        "PPA price. Guaranteed tariff = (PPA − grid fee − ancillary fee) × (1 − guarantee discount) "
        "+ subsidy price (within the subsidy years only)."),
    "tariff": (
        "实际上网电价，通常 = 基准电价（PPA）− 过网费 − 辅助服务费。",
        "Actual grid price: usually PPA minus grid fee and ancillary-service fee."),
    "market_price": (
        "市场化电量结算电价，默认取实际上网电价。",
        "Tariff for market-traded volume; defaults to the actual grid price."),
    "overgen_price": (
        "超发部分约定电价，默认取实际上网电价。",
        "Agreed tariff for excess generation; defaults to the actual grid price."),
    "storage_elec_price": (
        "储能上网电价。留空或填 0（默认）＝自动跟随「保障收购电价（实际上网电价）」；填正数则单独指定。"
        "储能上网收入 = 直流容量 × 储能等效小时 × 本电价。",
        "Storage feed-in tariff. Leave 0 (default) to follow the plant's actual grid price; "
        "enter a positive value to override."),
    "storage_lease_price": (
        "储能租赁电价。租赁收入 = 直流容量 × 配置比例 × 储能时长 × 本租赁价（不含年充放天数）；发电侧为 0。",
        "Storage lease tariff. Revenue = DC capacity × ratio × duration × this price (days excluded); "
        "0 on the generation side."),
}


FIELD_NOTES = {
    "om_cost_mode": {
        "自下而上分项": "人工/保险/维修/材料/土地等逐项累加，随下方各分项参数变动。",
        "投资额×比例": "年运维 = 项目总投资 × 费率，定额不设通胀（委托方 I-202610-007 口径）；下方自下而上分项暂不参与计算。",
    },
    "storage_rev_on": {
        "计储能上网收入": "储能等效小时单独计上网电量（按交流容量），并从电站发电小时中扣减。",
        "不计（并入电站）": "储能不单列电量收入，电站按全部小时计收（委托方 I-202610-007 口径）。",
    },
    "debt_base_mode": {
        "折旧基数（可抵押资产）": "借款额 = 折旧基数 × 债务占比（仅可抵押固定资产）。",
        "项目总投资": "借款额 = 项目总投资 × 债务占比（含建设期利息与流动资金）。",
    },
    "cost_method": {
        "定额": "维修费/材料费 = 元/kW 定额 × 直流装机 × 通胀系数；由「运维方式」决定用自维或外委费率。",
        "比例": "材料费仍按元/kW 定额；维修费 = 固定资产净值 × 质保期内外费率（自维/外委分别取值）。",
        "仅储能": "电站侧人工、维修、材料、保险、土地等全部不计，仅保留储能运维费用。",
    },
    "insurance_method": {
        "固定定额": "保险费 = 保险基数 × 固定费率。",
        "自定比率": "五档费率：1–5 年／6–10 年／11–15 年／16–20 年／21 年起各取一档。",
    },
    "repay_method": {
        "等额本息": "每期还本付息额相同（年金摊还），利息前高后低。",
        "等额本金": "每期还本额相同，利息随余额递减。",
    },
    "om_mode": {
        "自维": "自有人员 + 自维材料费/维修费率。",
        "外委": "外委人员 + 外委材料费/维修费率，可另计固定年费。",
    },
    "tax_holiday_mode": {
        "直接免税": "运营前 N 年所得税全免，N = 优惠税率年限。",
        "三免三减半": "前 3 年全免、第 4–6 年减半、第 7 年起全额。",
    },
    "gen_type": {
        "光伏": "决策信息模版按光伏分项（组件/逆变器/支架/桩基…）生成。",
        "风电": "决策信息模版按风电分项（风机/塔筒/吊装/集电线路…）生成。",
    },
    "tariff_incl_tax": {
        "是": "收入按含税价计，再剥离销项税与销售税。",
        "否": "收入按不含税价计。",
    },
    "plant_type": {
        "陆上/光伏储能": "陆上电站；不计海域使用金。",
        "海上": "海上风电；按年计取海域使用金。",
    },
    "wacc_ccy": {
        "CNY": "折现率币种须与现金流币种一致；本项目现金流为人民币，人民币套即模型口径。",
        "USD": "美元套为对照：以美元 WACC 折现人民币现金流；WACC 高于项目 IRR 时 NPV 必然为负，属正常。",
        "LOCAL": "本国货币套为对照：本币 10Y 随国别自动取数；同以本币 WACC 折现人民币现金流。",
    },
}


# ── 中英文对照表（中文显示串 → 英文）─────────────────────────────────
EN = {
    # 参数分组
    "基本情形": "General", "装机与发电": "Capacity & Generation", "电价": "Tariffs",
    "储能": "Storage", "投资": "Investment", "折旧": "Depreciation",
    "运营成本": "Operating Costs", "融资": "Financing", "税务": "Taxation",
    "折现与风险 (CAPM)": "Discounting & Risk (CAPM)",
    "折现与风险 (WACC)": "Discounting & Risk (WACC)",
    "项目所在国": "Country", "所属行业（取 βu）": "Sector (sets βu)",
    "WACC 采用币种": "WACC Currency", "Rd 确定方式": "Rd Method",
    "本币无风险利率": "Local Risk-Free Rate", "投资人指定 Rd": "Investor-specified Rd",
    "决策模板单价（光伏）": "Decision Template Prices (PV)",
    "决策模板单价（风电）": "Decision Template Prices (Wind)",
    # 参数字段
    "情景预设": "Scenario", "发电类型": "Generation Type", "电站类型": "Plant Type",
    "项目名称（中文）": "Project Name (CN)", "项目名称（英文）": "Project Name (EN)",
    "电池类型": "Battery Type", "投产年": "COD Year", "建设期": "Construction Period",
    "运营期": "Operating Period", "海域使用金": "Sea Area Use Fee",
    "交流装机": "AC Capacity", "直流装机": "DC Capacity",
    "铭牌利用小时": "Nameplate Hours", "实际发电小时": "Actual Generation Hours",
    "线损率": "Line Loss Rate", "保障收购小时": "Guaranteed Purchase Hours",
    "市场化交易小时": "Market Trading Hours", "首年折减": "First-Year Haircut",
    "组件年衰减": "Annual Degradation", "保障收购电价": "Guaranteed Tariff",
    "基准电价": "Benchmark Tariff", "保障电价折让": "Guaranteed Tariff Discount",
    "差价补贴单价": "Subsidy Price", "差价补贴年限": "Subsidy Years",
    "市场化电价": "Market Price",
    "超发电价": "Excess Generation Price", "储能上网电价": "Storage Feed-in Tariff",
    "过网费": "Grid Fee", "辅助服务费": "Ancillary Service Fee",
    "电价是否含税": "Tariff Includes Tax",
    "配置比例": "Storage Ratio", "有效容量系数": "Available Capacity Factor",
    "储能时长": "Storage Duration", "年充放天数": "Cycle Days per Year",
    "电芯可用小时": "Cell Usable Hours", "储能效率": "Round-trip Efficiency",
    "租赁比例": "Leased Share", "租赁价格": "Lease Price",
    "储能单价": "Storage Unit Price",
    "储能 EPC 单价": "Storage EPC Unit Price", "电芯更换单价": "Cell Replacement Price",
    "储能运维人员": "Storage O&M Staff", "储能外委人员": "Storage Outsourced Staff",
    "储能管理费率": "Storage Management Fee",
    "储能自维材料费(质保内)": "Storage In-house Materials (in warranty)",
    "储能自维材料费(质保外)": "Storage In-house Materials (out of warranty)",
    "储能自维维修费(质保内)": "Storage In-house Repair (in warranty)",
    "储能自维维修费(质保外)": "Storage In-house Repair (out of warranty)",
    "储能外委材料费(质保内)": "Storage Outsourced Materials (in warranty)",
    "储能外委材料费(质保外)": "Storage Outsourced Materials (out of warranty)",
    "储能外委维修费(质保内)": "Storage Outsourced Repair (in warranty)",
    "储能外委维修费(质保外)": "Storage Outsourced Repair (out of warranty)",
    "储能自维其他费(质保内)": "Storage In-house Other (in warranty)",
    "储能自维其他费(质保外)": "Storage In-house Other (out of warranty)",
    "储能外委其他费(质保内)": "Storage Outsourced Other (in warranty)",
    "储能外委其他费(质保外)": "Storage Outsourced Other (out of warranty)",
    "单位建设投资": "Unit Capex", "流动资金": "Working Capital",
    "电站 EPC 总价": "Station EPC Contract",
    "电站建设管理费率": "Station Management Fee",
    "电站管理费率(回退)": "Station Fee Rate (Fallback)",
    "储能建设管理费率": "Storage Management Fee",
    "设备单价（备查）": "Equipment Price (Memo)",
    "无形及递延资产": "Intangibles & Deferred", "摊销年限": "Amortization Life",
    "折旧年限": "Depreciation Life", "残值率": "Salvage Rate",
    "退役拆除费率": "Decommissioning Ratio",
    "运维方式": "O&M Mode", "成本方法": "Cost Method",
    "运维成本口径": "O&M Cost Basis", "投资额比例法费率": "O&M % of Investment",
    "储能上网收入": "BESS Grid Revenue", "债务基数口径": "Debt Base",
    "全投资初始投入": "Project CF Initial Outlay",
    "自下而上分项": "Bottom-up items", "投资额×比例": "Investment × %",
    "计储能上网收入": "Count BESS revenue", "不计（并入电站）": "Exclude (merged into plant)",
    "折旧基数（可抵押资产）": "Depreciation base (pledgeable assets)", "项目总投资": "Total project investment",
    "不含建设期利息": "Excl. IDC", "含建设期利息": "Incl. IDC",
    "质保年限": "Warranty Years", "自有人员配置": "In-house Staff",
    "外委人员配置": "Outsourced Staff", "人均年薪": "Average Salary",
    "福利比例": "Benefits Ratio", "项目占地": "Land Area",
    "土地租金标准": "Land Rent", "汇率": "FX Rate", "其他费用": "Other Costs",
    "土地补偿": "Land Compensation",
    "征地补偿标准": "Land Acquisition Rate",
    "土地使用税": "Land Use Tax", "土地税计税基础": "Land Tax Base",
    "土地税率": "Land Tax Rate",
    "房产税率": "Property Tax Rate", "储能其他运维费": "Storage Other O&M",
    "成本年涨幅": "Cost Inflation",
    "自维材料费(质保内)": "In-house Materials (in warranty)",
    "自维材料费(质保外)": "In-house Materials (out of warranty)",
    "自维维修费(质保内)": "In-house Repair (in warranty)",
    "自维维修费(质保外)": "In-house Repair (out of warranty)",
    "外委材料费(质保内)": "Outsourced Materials (in warranty)",
    "外委材料费(质保外)": "Outsourced Materials (out of warranty)",
    "外委维修费(质保内)": "Outsourced Repair (in warranty)",
    "外委维修费(质保外)": "Outsourced Repair (out of warranty)",
    "自维其他费(质保内)": "In-house Other (in warranty)",
    "自维其他费(质保外)": "In-house Other (out of warranty)",
    "外委其他费(质保内)": "Outsourced Other (in warranty)",
    "外委其他费(质保外)": "Outsourced Other (out of warranty)",
    "自维维修费率(质保内)": "In-house Repair Rate (in warranty)",
    "自维维修费率(质保外)": "In-house Repair Rate (out of warranty)",
    "外委维修费率(质保内)": "Outsourced Repair Rate (in warranty)",
    "外委维修费率(质保外)": "Outsourced Repair Rate (out of warranty)",
    "外委固定年费": "Outsourced Fixed Fee", "保险费方式": "Insurance Method",
    "保险费率(首档)": "Insurance Rate (Tier 1)",
    "保险费率(第2档)": "Insurance Rate (Tier 2)",
    "保险费率(第3档)": "Insurance Rate (Tier 3)",
    "保险费率(第4档)": "Insurance Rate (Tier 4)",
    "保险费率(第5档)": "Insurance Rate (Tier 5)",
    "保险固定费率": "Fixed Insurance Rate", "债务占比": "Debt Ratio",
    "债务利率": "Debt Rate", "借款期限": "Debt Tenor",
    "还本方式": "Repayment Method", "DSRA 月数": "DSRA Months",
    "流贷利率": "WC Loan Rate", "流贷占比": "WC Loan Ratio",
    "所得税率": "Income Tax Rate", "免税方式": "Tax Holiday Mode",
    "优惠税率年限": "Preference Years", "预扣税率": "Withholding Rate",
    "盈余公积比例": "Reserve Ratio", "增值税率": "VAT Rate",
    "增值税免税年限": "VAT Exemption Years", "销售税率": "Sales Tax Rate (only if tariff incl. tax)",
    "其他特别费用": "Other Special Fees (manual)",
    "其他特别费用方式": "Other Special Fees Mode",
    "其他特别费用比例": "Other Special Fees Rate",
    "其他特别费用金额": "Other Special Fees Amount",
    "按发电收入百分比": "% of Revenue", "固定金额": "Fixed Amount",
    "销售税免税年限": "Sales Tax Exemption Years",
    "城建税率": "City Construction Tax", "教育附加率": "Education Surcharge",
    "增值税返还": "VAT Refund", "无杠杆 βu": "Unlevered Beta βu",
    "无风险利率": "Risk-Free Rate", "股权风险溢价 ERP": "Equity Risk Premium ERP",
    "国别风险溢价 CRP": "Country Risk Premium CRP", "债务成本 Rd": "Cost of Debt Rd",
    "光伏组件": "PV Modules", "汇流箱/箱变": "Combiner Box / Transformer",
    "逆变器": "Inverters", "支架": "Mounting Structure", "桩基": "Piles",
    "电缆": "Cables", "通讯监控": "Communication & Monitoring",
    "设备安装": "Equipment Installation", "电气安装": "Electrical Installation",
    "调试": "Commissioning", "基础": "Foundations", "围栏": "Fencing",
    "升压站": "Booster Station", "勘察设计": "Survey & Design",
    "运输": "Freight", "境内税费": "Domestic Taxes", "其他": "Others",
    "风电机组": "Wind Turbines", "塔筒": "Towers",
    "电气设备": "Electrical Equipment", "土建": "Civil Works",
    "安装": "Installation", "道路": "Roads", "集电线路": "Collection Lines",
    "吊装": "Hoisting",
    # 选项
    "基准": "Base", "保守": "Conservative", "乐观": "Optimistic",
    "光伏": "Solar PV", "风电": "Wind", "陆上/光伏储能": "Onshore / PV+Storage",
    "海上": "Offshore", "否": "No", "是": "Yes", "自维": "In-house",
    "外委": "Outsourced", "定额": "Fixed Quota", "比例": "Ratio",
    "磷酸铁锂": "LFP", "三元锂": "NMC", "液流电池": "Flow Battery",
    "仅储能": "Storage Only", "固定定额": "Fixed Amount",
    "自定比率": "Custom Ratio", "等额本息": "Equal Payment",
    "等额本金": "Equal Principal", "直接免税": "Direct Exemption",
    "三免三减半": "3+3 Holiday",
    # 指标卡
    "全投资 IRR（税后）": "Project IRR (after tax)",
    "全投资 MIRR": "Project MIRR",
    "资本金 MIRR": "Equity MIRR",
    "全投资 IRR（税前）": "Project IRR (before tax)",
    "资本金 IRR": "Equity IRR", "全投资 NPV": "Project NPV",
    "全投资 NPV（万元）": "Project NPV (¥10k)",
    "资本金 NPV": "Equity NPV", "资本金 NPV（万元）": "Equity NPV (¥10k)",
    "LCOE": "LCOE", "全投资回收期": "Project Payback",
    "资本金回收期（年）": "Equity Payback (yrs)",
    "全投资回收期（年）": "Project Payback (yrs)",
    "最小 DSCR": "Min DSCR", "平均 DSCR": "Avg DSCR", "最高 ICR": "Max ICR",
    "平均 ICR": "Avg ICR", "最低 ICR": "Min ICR",
    "峰值资产负债率": "Peak Gearing", "总投资": "Total Investment",
    "权益资金": "Equity", "单位造价": "Unit Cost",
    "折现率 WACC": "Discount Rate (WACC)", "平均 ROE": "Avg ROE",
    "单位造价（元/W）": "Unit Cost (¥/W)",
    "LCOE（元/kWh）": "LCOE (¥/kWh)",
    "LCOE（元/kWh）": "LCOE (¥/kWh)",
    "全期营业收入（万元）": "Lifetime Revenue (¥10k)",
    "全期经营成本（万元）": "Lifetime Opex (¥10k)",
    "债务资金（万元）": "Debt (¥10k)",
    "收益": "Returns", "偿债": "Debt Service", "规模": "Scale",
    "回报": "Profitability",
    # 报表名
    "损益表": "P&L Statement", "全部投资现金流": "Project Cash Flow",
    "资本金现金流": "Equity Cash Flow", "还本付息表": "Debt Service",
    "销售收入": "Revenue", "资产负债表": "Balance Sheet",
    "总成本表": "Total Cost", "资金筹措": "Funding",
    "摊销表": "Amortization", "财务计划": "Financial Plan",
    "决策信息模版": "Decision Template", "WACC敏感度": "WACC Sensitivity",
    "WACC三币种对比": "WACC Currency Comparison",
    "LCOE计算表": "LCOE Calculation", "WACC计算表": "WACC Calculation",
    # 列名
    "项目年": "Project Year", "运营年": "Operating Year",
    "营业收入": "Revenue", "销售税及附加": "Sales Tax & Surcharge",
    "经营成本": "Operating Cost", "摊销": "Amortization", "利息": "Interest",
    "成本费用合计": "Total Cost", "税前利润": "Pre-tax Profit",
    "所得税": "Income Tax", "净利润": "Net Profit",
    "预扣税": "Withholding Tax", "可分配利润": "Distributable Profit",
    "建设投资": "Construction Investment",
    "建设投资（不含建设期利息）": "Construction Investment (excl. IDC)",
    "建设期利息": "Interest During Construction",
    "无形及递延资产": "Intangibles & Deferred Assets",
    "地方提留": "Local Levy",
    "调整所得税": "Adjusted Income Tax",
    "回收固定资产余值": "Salvage Value", "回收流动资金": "WC Recovery",
    "净现金流量": "Net Cash Flow", "累计净现金流量": "Cumulative NCF",
    "还本": "Principal", "流动资金还款": "WC Repayment",
    "可抵扣增值税形成资产": "Deductible VAT Asset",
    "DSRA 净变动": "DSRA Change", "期初借款": "Opening Debt",
    "提款": "Drawdown", "期末借款": "Closing Debt",
    "还本付息": "Debt Service", "DSRA 余额": "DSRA Balance",
    "等效小时": "Equivalent Hours", "发电量(万kWh)": "Generation (10k kWh)",
    "保障电量": "Guaranteed Energy", "超发电量": "Excess Energy",
    "市场化电量": "Market Energy", "储能电量": "Storage Energy",
    "保障收入": "Guaranteed Revenue", "超发收入": "Excess Revenue",
    "市场化收入": "Market Revenue", "储能收入": "Storage Revenue",
    "收入合计": "Total Revenue", "货币资金": "Cash",
    "在建工程": "Construction in Progress",
    "固定资产净值": "Net Fixed Assets", "无形递延净值": "Net Intangibles",
    "资产总计": "Total Assets", "借款余额": "Debt Balance",
    "流贷余额": "WC Loan Balance", "实收资本": "Paid-in Capital",
    "盈余公积": "Surplus Reserve", "未分配利润": "Retained Earnings",
    "负债及权益": "Liabilities & Equity", "平衡差异": "Balance Check",
    "工资福利": "Payroll & Benefits", "维修费": "Maintenance",
    "材料费": "Materials", "保险费": "Insurance",
    "土地相关": "Land-related", "房产税": "Property Tax",
    "储能运维": "Storage O&M", "经营成本合计": "Total Operating Cost",
    "资本金投入": "Equity Injection", "长期借款": "Long-term Loan",
    "流动资金借款": "WC Loan",
    "建设期利息(资本化)": "IDC (capitalized)",
    "资金来源合计": "Total Funding", "长期借款余额": "LT Loan Balance",
    "权益余额": "Equity Balance", "折旧基数": "Depreciation Base",
    "年折旧率": "Annual Depreciation Rate", "年折旧额": "Annual Depreciation",
    "累计折旧": "Accumulated Depreciation", "期末净值": "Closing NBV",
    "摊销基数": "Amortization Base", "年摊销率": "Annual Amortization Rate",
    "年摊销额": "Annual Amortization", "累计摊销": "Accumulated Amortization",
    "经营活动": "Operating Activities", "投资活动": "Investing Activities",
    "筹资活动": "Financing Activities", "现金净变动": "Net Cash Change",
    "期末现金": "Closing Cash", "勾稽差异": "Reconciliation Check",
    # 特殊表
    "一、光伏发电工程": "I. PV Works",
    "一、风力发电工程": "I. Wind Works", "二、储能工程": "II. Energy Storage",
    "三、技术经济指标": "III. Technical & Economic Indicators",
    "四、投资与财务指标": "IV. Investment & Financial Indicators",
    "分项小计": "Subtotal", "储能系统": "Storage System",
    "储能容量": "Storage Capacity", "首年发电量": "First-Year Generation",
    "首年等效小时": "First-Year Hours", "年均发电量": "Average Generation",
    "电站投资": "Station Investment", "储能投资": "Storage Investment",
    "电站单位造价": "Station Unit Cost", "储能单位造价": "Storage Unit Cost",
    "平均运维成本": "Average O&M Cost", "最低 DSCR": "Min DSCR",
    "WACC": "WACC", "项目": "Item", "数值": "Value", "单位": "Unit",
    "单价 / 说明": "Price / Note", "说明": "Note", "指标": "Metric",
    # LCOE / WACC 行
    "运营成本现值": "PV of Operating Costs", "折旧抵税现值": "PV of Tax Shield",
    "残值现值": "PV of Salvage", "分子合计": "Numerator",
    "发电量现值": "PV of Generation", "权益占比 E/V": "Equity Share E/V",
    "债务占比 D/V": "Debt Share D/V", "所得税率 Tc": "Tax Rate Tc",
    "杠杆 βL": "Levered βL", "无风险利率 Rf": "Risk-Free Rate Rf",
    "股权风险溢价 ERP": "Equity Risk Premium ERP",
    "国别风险溢价 CRP": "Country Risk Premium CRP",
    "权益成本 Re": "Cost of Equity Re", "税后债务成本": "After-tax Cost of Debt",
    "折现率": "Discount Rate",
    # 短说明
    "按上述单价汇总": "Sum of unit prices above",
    "含建设期利息与流动资金": "Incl. IDC and working capital",
    "建设投资扣除储能": "Construction investment less storage",
    "经营成本年均值": "Average annual operating cost",
    "静态": "Static", "CAPM 口径": "CAPM basis",
    "建设投资 + 建设期利息 + 流动资金": "Construction investment + IDC + WC",
    "经营成本 + 销售税及附加，折现": "Operating cost + sales tax & surcharge, discounted",
    "折旧与摊销 × 所得税率，折现（减项）": "Depreciation & amortization × tax rate, discounted (deduct)",
    "期末固定资产余值折现（减项）": "Terminal salvage value, discounted (deduct)",
    "总投资 + 运营成本现值 − 抵税 − 残值": "Total investment + PV opex − tax shield − salvage",
    "运营期发电量逐年折现": "Operating-period generation, discounted",
    "分子合计 ÷ 发电量现值 ÷ 1e4": "Numerator ÷ PV generation ÷ 1e4",
    "1 − 债务占比": "1 − debt ratio", "债务占比": "Debt ratio",
    "行业无杠杆贝塔": "Industry unlevered beta",
    "βu × [1 + (1−Tc) × D/E]": "βu × [1 + (1−Tc) × D/E]",
    "美元 10 年期国债": "USD 10-year Treasury",
    "总 ERP − CRP": "Total ERP − CRP", "Rf + βL × ERP + CRP": "Rf + βL × ERP + CRP",
    "投资人指定": "Specified by investor",
    "Rd × (1 − Tc)": "Rd × (1 − Tc)",
    "E/V × Re + D/V × Rd × (1 − Tc)": "E/V × Re + D/V × Rd × (1 − Tc)",
    # —— 储能接入位置 ——
    "储能接入位置": "Storage Connection",
    "发电侧": "Generation side",
    "电网侧": "Grid side",
    # —— 单位（Wp/Wh 口径）——
    "交流装机（AC）": "AC Capacity",
    "直流装机（DC）": "DC Capacity",
    "单位造价（元/Wp）": "Unit Cost (CNY/Wp)",
    "元/Wp(DC)": "CNY/Wp (DC)",
    "元/kWp(DC)": "CNY/kWp (DC)",
    "元/Wp": "CNY/Wp",
    "电站运维": "Station O&M",
    "储能运维": "Storage O&M",
    "前期咨询费": "Pre-development Consulting Fee",
    "项目前期开发费": "Pre-development Cost",
    "元/Wp": "CNY/Wp",
    "收入合计（不含税）": "Total Revenue (ex-VAT)",
    "销项税额": "Output VAT",
    "收入合计（含税）": "Total Revenue (VAT incl.)",
    "储能收入合计": "Storage Revenue Total",
    "　其中：补贴收入": "  of which: Subsidy Revenue",
    "补贴收入": "Subsidy Revenue",
    "计价货币": "Display Currency",
    "界面语言": "Interface Language",
    "界面语言（主）": "Interface Language (Primary)",
    "界面语言（副/对照）": "Interface Language (Secondary)",
    "无（单语言）": "None (single language)",
    "人民币 CNY": "CNY",
    "美元 USD": "USD",
    "万美元": "10K USD",
    # —— 增值税 ——
    "增值税计算表": "VAT Calculation",
    "期初留抵": "Opening VAT Credit",
    "销项税额": "Output VAT",
    "进项税额(运营)": "Input VAT (Opex)",
    "减：可抵扣进项税": "Less: Creditable Input VAT",
    "经营成本合计（含税）": "Total Operating Cost (VAT-incl.)",
    "经营成本（不含税）": "Operating Cost (ex-VAT)",
    "抵扣留抵": "VAT Credit Used",
    "应交增值税": "VAT Payable",
    "附加税": "Surcharge",
    "期末留抵": "Closing VAT Credit",
    # —— 电价与小时数（2026-10-23 收入重构）——
    "首年发电小时数": "First-Year Generation Hours",
    "市场化交易小时数": "Market Trading Hours",
    "超发小时数": "Excess Generation Hours",
    "储能等效小时数": "Storage Equivalent Hours",
    "首年保障收购小时数": "Guaranteed Hours (Year 1)",
    "基准电价（PPA）": "Benchmark Tariff (PPA)",
    "保障收购电价（实际上网电价）": "Guaranteed Tariff (actual grid price)",
    "市场化交易电价": "Market Tariff",
    "超发电价": "Excess Generation Tariff",
    "储能上网电价": "Storage Feed-in Tariff",
    # —— 补充对照（2026-10-23）——
    "储能配置时长": "Storage Duration",
    "储能配置比例": "Storage Ratio",
    "电站 EPC 单价": "Station EPC Unit Price",
    "元/W(直流)": "CNY/W (DC)",
    "元/W": "CNY/W",
    "储能上网收入": "Storage Feed-in Revenue",
    "储能收入合计": "Storage Revenue Total",
    "储能租赁收入": "Storage Lease Revenue",
    "折旧表": "Depreciation",
    "储能总投资": "Storage Total Investment",
    "储能全生命周期总投资": "Storage Lifetime Total Investment",
    "储能全寿命周期总投资": "Storage Lifetime Total Investment",
    "储能 EPC 总价（初始投资）": "Storage EPC (initial investment)",
    "储能初始总投资": "Storage Initial Total Investment",
    "电站总投资": "Station Total Investment",
    "项目总投资": "Total Investment",
    "储能 EPC 总价": "Storage EPC Price",
    "储能业主管理费": "Storage Owner Mgmt Fee",
    "储能业主管理费（EPC 之外另计）": "Storage Owner Mgmt Fee (on top of EPC)",
    "电站业主管理费": "Station Owner Mgmt Fee",
    "电站业主管理费（EPC 之外另计）": "Station Owner Mgmt Fee (on top of EPC)",
    "每千瓦投资": "Investment per kW",
    "储能接入位置（在「基本情形」设置）": "Storage Connection (set in General)",
    "配置时长（在「基本情形」设置）": "Storage Duration (set in General)",
    "配置比例（在「基本情形」设置）": "Storage Ratio (set in General)",
    "项目总投资（电站+储能+利息+流动资金）": "Total Investment (station + storage + IDC + working capital)",
    # —— 单位（parameter units）——
    "年": "yr",
    "月": "month",
    "万元": "10K CNY",
    "万元/年": "10K CNY/yr",
    "MW": "MW",
    "h": "h",
    "h/年": "h/yr",
    "h/年（0=自动）": "h/yr (0=auto)",
    "%": "%",
    "%/年": "%/yr",
    "%（末年末）": "% (final yr)",
    "元/kWh": "CNY/kWh",
    "元/Wh": "CNY/Wh",
    "元/kWp": "CNY/kW",
    "元/kW(直流)": "CNY/kW (DC)",
    "元/kWp·年": "CNY/kW·yr",
    "元/MWh·年": "CNY/MWh·yr",
    "天/年": "days/yr",
    "人/100MWh": "staff/100MWh",
    "人/100MW": "staff/100MW",
    "人/50MW": "staff/50MW",
    "万元/人·年": "10K CNY/person·yr",
    "公顷": "ha",
    "美元/公顷·年": "USD/ha·yr",
    "元/美元": "CNY/USD",
    "元/平方米": "CNY/m²",
}

NOTES_EN = {
    "cost_method": {
        "定额": "Repair/materials = CNY/kW quota × DC capacity × inflation; in-house or outsourced rates follow O&M Mode.",
        "比例": "Materials use the quota; repair = net fixed assets × in/out-of-warranty rate (in-house or outsourced).",
        "仅储能": "All station-side labor, repair, material, insurance and land costs are excluded; storage O&M only.",
    },
    "insurance_method": {
        "固定定额": "Insurance = insurance base × fixed rate.",
        "自定比率": "Five tiers: years 1–5 / 6–10 / 11–15 / 16–20 / 21+ each use one rate.",
    },
    "repay_method": {
        "等额本息": "Constant debt service (annuity); interest is front-loaded.",
        "等额本金": "Constant principal; interest declines with the outstanding balance.",
    },
    "om_mode": {
        "自维": "In-house staff + in-house material/repair rates.",
        "外委": "Outsourced staff + outsourced material/repair rates; optional fixed annual fee.",
    },
    "tax_holiday_mode": {
        "直接免税": "Income tax fully exempt for the first N years (N = preference years).",
        "三免三减半": "Years 1–3 exempt, years 4–6 at half rate, full rate from year 7.",
    },
    "gen_type": {
        "光伏": "Decision Template itemizes PV components (modules, inverters, structures, piles…).",
        "风电": "Decision Template itemizes wind components (turbines, towers, hoisting, collection lines…).",
    },
    "tariff_incl_tax": {
        "是": "Revenue is booked at tax-inclusive prices; output VAT and sales tax are then stripped.",
        "否": "Revenue is booked at tax-exclusive prices.",
    },
    "plant_type": {
        "陆上/光伏储能": "Onshore station; no sea area use fee.",
        "海上": "Offshore wind; annual sea area use fee applies.",
    },
    "wacc_ccy": {
        "CNY": "Discount-rate currency must match the cash-flow currency; cash flows are in CNY, so the CNY set is the model basis.",
        "USD": "USD set is a comparison: it discounts CNY cash flows at the USD WACC; NPV is negative whenever WACC exceeds project IRR — expected.",
        "LOCAL": "Local set is a comparison: local 10Y is auto-filled by country; it discounts CNY cash flows at the local-currency WACC.",
    },
}


def en(s):
    """中文显示串 → 英文（无对照时返回空串）。"""
    return EN.get(s, "")


def bi(s, sep="\n"):
    """中文 + 英文两行显示；无英文时原样返回。"""
    e = EN.get(s)
    return f"{s}{sep}{e}" if e and e != s else s


def en_list(items):
    return [EN.get(x, "") for x in items]


# ── 年度报表 ──────────────────────────────────────────────────────────
def _capex_invest(m, extra, i):
    return -m["p"]["fixed_asset_capex"] / m["t"] if i < m["t"] else 0.0


def _wc_invest(m, extra, i):
    return -m["p"]["working_capital"] if i == m["t"] - 1 else 0.0


def _salvage_rec(m, extra, i):
    return m["salvage_value"] if i == m["last"] else 0.0


def _wc_recover(m, extra, i):
    return m["p"]["working_capital"] if i == m["last"] else 0.0


def _equity_in(m, extra, i):
    return -float(m["equity_cf"][i])


def _idc_cap(m, extra, i):
    return m["p"]["idc"] / m["t"] if i < m["t"] else 0.0


TABLE_SPECS = [
    ("损益表", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("revenue", "营业收入", 95, "f1"),
        ("tax_surcharge", "销售税及附加", 100, "f1"),
        ("local_levy", "地方提留", 90, "f1"),
        ("opex_ex_vat", "经营成本（不含税）", 115, "f1"),
        ("dep", "折旧", 85, "f1"),
        ("amort", "摊销", 80, "f1"),
        ("interest_total", "利息", 90, "f1"),
        ("total_cost", "成本费用合计", 105, "f1"),
        ("ebit", "EBIT", 90, "f1"),
        ("ebt", "税前利润", 95, "f1"),
        ("tax", "所得税", 90, "f1"),
        ("ni", "净利润", 95, "f1"),
        ("withholding", "预扣税", 85, "f1"),
        ("distributable", "可分配利润", 105, "f1"),
    ]),
    ("全部投资现金流", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("_capex", "建设投资（不含建设期利息）", 130, "f1"),
        ("_other_asset", "无形及递延资产", 110, "f1"),
        ("_wc", "流动资金", 90, "f1"),
        ("revenue", "营业收入", 95, "f1"),
        ("opex_cf", "经营成本（不含税）", 115, "f1"),
        ("tax_surcharge_cf", "销售税及附加", 100, "f1"),
        ("local_levy_cf", "地方提留", 90, "f1"),
        ("vat_cash_net", "增值税净额", 95, "f1"),
        ("repl_cf", "电芯更换投资", 110, "f1"),
        ("tax_project", "调整所得税", 100, "f1"),
        ("_salvage", "回收固定资产余值", 125, "f1"),
        ("_wcrec", "回收流动资金", 110, "f1"),
        ("cf_project", "净现金流量", 105, "f1"),
        ("cum_p", "累计净现金流量", 120, "f1"),
    ]),
    ("资本金现金流", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("equity_cf", "资本金投入", 105, "f1"),
        ("ni", "净利润", 90, "f1"),
        ("dep", "折旧", 85, "f1"),
        ("amort", "摊销", 80, "f1"),
        ("principal_cf", "还本", 90, "f1"),
        ("wc_repay_cf", "流动资金还款", 110, "f1"),
        ("dsra_delta", "DSRA 净变动", 105, "f1"),
        ("vat_cash_net", "增值税净额", 95, "f1"),
        ("repl_cf", "电芯更换投资", 110, "f1"),
        ("withholding_cf", "预扣税", 85, "f1"),
        ("_salvage", "回收固定资产余值", 125, "f1"),
        ("_wcrec", "回收流动资金", 110, "f1"),
        ("cf_equity", "净现金流量", 105, "f1"),
        ("cum_e", "累计净现金流量", 120, "f1"),
    ]),
    ("还本付息表", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("opening", "期初借款", 105, "f1"),
        ("draw", "提款", 90, "f1"),
        ("interest_total", "利息", 90, "f1"),
        ("principal", "还本", 95, "f1"),
        ("closing", "期末借款", 105, "f1"),
        ("cfads", "CFADS", 95, "f1"),
        ("debt_service", "还本付息", 100, "f1"),
        ("dscr", "DSCR", 75, "f2"),
        ("icr", "ICR", 75, "f2"),
        ("dsra_bal", "DSRA 余额", 95, "f1"),
    ]),
    ("销售收入", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("h_plant", "电站等效小时", 95, "f1"),
        ("h_storage", "储能等效小时", 95, "f1"),
        ("gen_plant", "电站上网电量(万kWh)", 120, "f1"),
        ("gen_guar", "保障电量", 90, "f1"),
        ("gen_over", "超发电量", 90, "f1"),
        ("gen_mkt", "市场化电量", 95, "f1"),
        ("gen_storage", "储能电量", 90, "f1"),
        ("rev_guaranteed", "保障收入", 95, "f1"),
        ("rev_subsidy", "　其中：补贴收入", 115, "f1"),
        ("rev_overgen", "超发收入", 95, "f1"),
        ("rev_market", "市场化收入", 100, "f1"),
        ("rev_storage_gen", "储能上网收入", 105, "f1"),
        ("rev_storage_lease", "储能租赁收入", 105, "f1"),
        ("rev_storage", "储能收入合计", 100, "f1"),
        ("revenue", "收入合计（不含税）", 115, "f1"),
        ("output_vat", "销项税额", 95, "f1"),
        ("revenue_incl", "收入合计（含税）", 115, "f1"),
    ]),
    ("增值税计算表", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("vat_credit_open", "期初留抵", 100, "f1"),
        ("output_vat", "销项税额", 100, "f1"),
        ("input_vat_op", "进项税额(运营)", 110, "f1"),
        ("vat_credit_used", "抵扣留抵", 100, "f1"),
        ("vat_payable", "应交增值税", 105, "f1"),
        ("surtax", "附加税", 90, "f1"),
        ("vat_credit_close", "期末留抵", 100, "f1"),
    ]),
    ("资产负债表", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("cash", "货币资金", 100, "f1"),
        ("cip", "在建工程", 100, "f1"),
        ("nbv_bs", "固定资产净值", 110, "f1"),
        ("amort_bs", "无形递延净值", 110, "f1"),
        ("wc", "流动资金", 90, "f1"),
        ("dsra_bal", "DSRA", 90, "f1"),
        ("vat_asset", "可抵扣增值税形成资产", 90, "f1"),
        ("total_assets", "资产总计", 110, "f1"),
        ("debt_bal", "借款余额", 100, "f1"),
        ("wc_open", "流贷余额", 90, "f1"),
        ("equity_bal", "实收资本", 100, "f1"),
        ("reserve_cum", "盈余公积", 95, "f1"),
        ("re", "未分配利润", 105, "f1"),
        ("total_le", "负债及权益", 110, "f1"),
        ("bs_check", "平衡差异", 100, "f4"),
    ]),
    ("总成本表", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("payroll", "工资福利", 90, "f1"),
        ("maint", "维修费", 90, "f1"),
        ("material", "材料费", 90, "f1"),
        ("other", "其他费用", 90, "f1"),
        ("insurance", "保险费", 85, "f1"),
        ("land", "土地相关", 90, "f1"),
        ("property_tax", "房产税", 85, "f1"),
        ("storage_opex", "储能运维", 90, "f1"),
        ("sea_fee", "海域使用金", 95, "f1"),
        ("opex", "经营成本合计（含税）", 115, "f1"),
        ("input_vat_ded", "减：可抵扣进项税", 120, "f1"),
        ("dep", "折旧", 85, "f1"),
        ("amort", "摊销", 80, "f1"),
        ("interest_total", "利息", 90, "f1"),
        ("total_cost", "成本费用合计", 105, "f1"),
    ]),
    ("资金筹措", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("_equityin", "资本金投入", 105, "f1"),
        ("draw", "长期借款", 95, "f1"),
        ("wc_draw", "流动资金借款", 110, "f1"),
        ("_idc", "建设期利息(资本化)", 130, "f1"),
        ("fund_total", "资金来源合计", 110, "f1"),
        ("closing", "长期借款余额", 110, "f1"),
        ("wc_open", "流贷余额", 90, "f1"),
        ("equity_bal", "权益余额", 100, "f1"),
    ]),
    ("折旧表", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("dep_base", "折旧基数", 100, "f1"),
        ("dep_rate", "年折旧率", 90, "f2"),
        ("dep", "年折旧额", 95, "f1"),
        ("cum_dep", "累计折旧", 95, "f1"),
        ("nbv", "期末净值", 95, "f1"),
    ]),
    ("摊销表", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("other_asset_base", "摊销基数", 100, "f1"),
        ("amort_rate", "年摊销率", 90, "f2"),
        ("amort", "年摊销额", 95, "f1"),
        ("cum_amort", "累计摊销", 95, "f1"),
        ("amort_bs", "期末净值", 95, "f1"),
    ]),
    ("财务计划", [
        ("yr", "项目年", 55, "int"), ("k", "运营年", 55, "op"),
        ("cfo", "经营活动", 105, "f1"),
        ("cfi", "投资活动", 105, "f1"),
        ("cff", "筹资活动", 105, "f1"),
        ("cash_cf", "现金净变动", 105, "f1"),
        ("cash", "期末现金", 105, "f1"),
        ("dsra_bal", "DSRA 余额", 95, "f1"),
        ("cash_cf_check", "勾稽差异", 100, "f4"),
    ]),
]

SERIES_NAMES = [name for name, _ in TABLE_SPECS]


# ── 术语表 ────────────────────────────────────────────────────────────
GLOSSARY = [
    ("IRR", "Internal Rate of Return", "内部收益率", "使项目净现值为零的折现率；全投资 IRR 不考虑融资结构"),
    ("Equity IRR", "Return on equity cash flows", "资本金 IRR", "按股东实际现金流出/流入计算的收益率"),
    ("NPV", "Net Present Value", "净现值", "按 WACC 折现的现金流现值之和；>0 表示超过基准回报"),
    ("WACC", "Weighted Average Cost of Capital", "加权平均资本成本", "股债加权折现率，本项目按 CAPM 合成"),
    ("DSCR", "Debt Service Coverage Ratio", "偿债备付率", "可用于还本付息的现金 ÷ 当期还本付息额"),
    ("ICR", "Interest Coverage Ratio", "利息保障倍数", "EBIT ÷ 利息支出"),
    ("LCOE", "Levelized Cost of Energy", "平准化度电成本", "全生命周期成本现值 ÷ 发电量现值，元/kWh"),
    ("EBITDA", "Earnings before interest, tax, depreciation & amortisation", "息税折旧摊销前利润", "经营性现金的近似口径"),
    ("EBIT", "Earnings before interest and tax", "息税前利润", "EBITDA − 折旧 − 摊销"),
    ("FCFF", "Free Cash Flow to Firm", "企业自由现金流", "全投资口径现金流（不扣融资）"),
    ("FCFE", "Free Cash Flow to Equity", "股权自由现金流", "扣除还本付息后的股东现金流"),
    ("CFADS", "Cash Flow Available for Debt Service", "可用于偿债的现金流", "DSCR 的分子"),
    ("PPA", "Power Purchase Agreement", "购电协议", "约定电价与电量的长期售电合同"),
    ("EPC", "Engineering, Procurement and Construction", "设计采购施工总承包", "本模型中电站与储能各自一个 EPC 总价"),
    ("COD", "Commercial Operation Date", "商业运行日", "本项目以投产年表示"),
    ("IDC", "Interest During Construction", "建设期利息", "建设期借款利息，计入总投资"),
    ("DSRA", "Debt Service Reserve Account", "偿债准备金账户", "按还本付息额留存的储备金"),
    ("O&M", "Operations and Maintenance", "运维", "含自维/外委两种方式"),
    ("OPEX", "Operating Expenditure", "经营成本", "人工、维修、材料、保险、土地等年度支出"),
    ("CAPEX", "Capital Expenditure", "建设投资", "电站 + 储能的 EPC 及管理费"),
    ("VAT", "Value Added Tax", "增值税", "销项 − 进项 − 留抵 = 应交；EPC 含税、可抵扣"),
    ("PIT", "Profit Income Tax", "企业所得税", "本模型按税率与免税年限计算"),
    ("Wp", "Watt-peak", "峰瓦", "光伏组件在标准测试条件下的峰值功率，直流侧计量"),
    ("kWp / MWp", "kilo/mega Watt-peak", "千瓦峰 / 兆瓦峰", "1 MWp = 1,000 kWp"),
    ("Wh / kWh / MWh", "Watt-hour", "瓦时 / 千瓦时 / 兆瓦时", "电量单位；储能容量与造价按 Wh 计"),
    ("DC", "Direct Current", "直流侧", "组件容量口径，本模型发电量按 DC 容量计"),
    ("AC", "Alternating Current", "交流侧", "并网点容量口径"),
    ("DC/AC ratio", "DC to AC capacity ratio", "容配比", "直流装机 ÷ 交流装机"),
    ("Degradation", "Annual output degradation", "年衰减率", "组件效率逐年下降，本模型按首年折减 + 年衰减"),
    ("Line loss", "Transmission line loss", "线损率", "上网电量按 (1−线损率) 折算"),
    ("Round-trip efficiency", "Storage round-trip efficiency", "储能效率", "充放电全过程效率"),
    ("Cycling days", "Equivalent full cycles per year", "年充放天数", "储能每年的等效满充满放次数"),
    ("Subsidy", "Feed-in tariff subsidy", "差价补贴", "补贴年限内叠加的度电补贴"),
    ("Tax holiday", "Corporate income tax holiday", "免税期", "直接免税 N 年，或三免三减半"),
]

def build_glossary():
    return {"type": "glossary", "title": "术语表", "title_en": "Glossary",
            "cols": ["缩写 / 术语", "英文全称", "中文", "说明"],
            "cols_en": ["Term", "Full name", "Chinese", "Note"],
            "rows": [list(r) for r in GLOSSARY]}

SPECIAL_TABLES = [
    ("术语表", "glossary"),
    ("决策信息模版", "decision"),
    ("LCOE计算表", "def"),
    ("WACC计算表", "combo"),
]

ALL_TABLE_NAMES = SERIES_NAMES + [name for name, _ in SPECIAL_TABLES]

# (键, 标题, 格式, 类别)
CARD_DEFS = [
    ("project_irr", "全投资 IRR（税后）", "pct", "收益"),
    ("mirr_project", "全投资 MIRR", "pct", "收益"),
    ("mirr_equity", "资本金 MIRR", "pct", "收益"),
    ("equity_irr", "资本金 IRR", "pct", "收益"),
    ("project_npv", "全投资 NPV", "num0", "收益"),
    ("equity_npv", "资本金 NPV", "num0", "收益"),
    ("lcoe", "LCOE", "raw4", "收益"),
    ("project_payback", "全投资回收期", "num1", "收益"),
    ("min_dscr", "最小 DSCR", "num2", "偿债"),
    ("avg_dscr", "平均 DSCR", "num2", "偿债"),
    ("min_icr", "最低 ICR", "num2", "偿债"),
    ("peak_debt_ratio", "峰值资产负债率", "pct", "偿债"),
    ("total_investment", "项目总投资", "num0", "规模"),
    ("station_invest", "电站总投资", "num0", "规模"),
    ("storage_invest", "储能全生命周期总投资", "num0", "规模"),
    ("equity_total", "权益资金", "num0", "规模"),
    ("unit_cost_w", "单位造价（元/Wp）", "num2", "规模"),
    ("wacc_capm", "折现率 WACC", "pct", "回报"),
    ("avg_roe", "平均 ROE", "pct", "回报"),
]

CARD_UNITS = {
    "project_irr": "", "equity_irr": "", "mirr_project": "", "mirr_equity": "", "project_npv": "万元",
    "equity_npv": "万元", "lcoe": "元/kWh", "project_payback": "年",
    "min_dscr": "×", "avg_dscr": "×", "min_icr": "×",
    "peak_debt_ratio": "", "total_investment": "万元",
    "station_invest": "万元", "storage_invest": "万元",
    "equity_total": "万元", "unit_cost_w": "元/Wp",
    "wacc_capm": "", "avg_roe": "",
}


def param_kind(key):
    for _, fields in GROUPS:
        for k, _, kind, _ in fields:
            if k == key:
                return kind
    return "float"


def param_label(key):
    for _, fields in GROUPS:
        for k, label, _, _ in fields:
            if k == key:
                return label
    return key


WACC_SELECT_KEYS = ("wacc_country", "wacc_sector", "wacc_ccy", "rd_method")


def display_value(key, val):
    """引擎取值 → 表单显示字符串。"""
    kind = param_kind(key)
    if key in WACC_SELECT_KEYS:
        return str(val)
    if kind == "choice":
        labs, mapping = CHOICES[key]
        return next((lab for lab in labs
                     if str(mapping[lab]) == str(val)), labs[0])
    if kind == "pct":
        return f"{float(val) * 100:.6g}"
    if kind == "text":
        return str(val)
    return f"{val:.6g}" if isinstance(val, float) else str(val)


# 当前版本界面上的全部参数键；其余键（旧记录里已删除的参数）在 coerce 时直接忽略，
# 否则会把 "电网侧" 这类文本当 float 解析而整模型报错。
KNOWN_KEYS = {k for _, fs in GROUPS for k, _, _, _ in fs}


def coerce_params(raw):
    """表单原始字符串 → 引擎参数（忽略已不存在的键）。"""
    p = {}
    for key, val in raw.items():
        if key not in KNOWN_KEYS:
            continue
        kind = param_kind(key)
        s = str(val).strip()
        if s == "" and kind not in ("text", "choice"):
            continue          # 留空＝用引擎默认值
        if key in ("wacc_country", "wacc_sector"):
            p[key] = s
        elif key == "wacc_ccy":
            mapping = {"CNY": "CNY", "USD": "USD", "LOCAL": "LOCAL",
                       "人民币 RMB": "CNY", "美元 USD": "USD",
                       "本国货币 Local": "LOCAL"}
            if s not in mapping:
                raise ValueError(f"「{param_label(key)}」取值无效：{s}")
            p[key] = mapping[s]
        elif key == "rd_method":
            mapping = {"1": 1, "0": 0, "是": 1, "否": 0,
                       "是（合成评级法）": 1, "否（投资人指定）": 0}
            if s not in mapping:
                raise ValueError(f"「{param_label(key)}」取值无效：{s}")
            p[key] = mapping[s]
        elif kind == "choice":
            labs, mapping = CHOICES[key]
            if s not in mapping:
                raise ValueError(f"「{param_label(key)}」取值无效：{s}")
            p[key] = mapping[s]
        elif kind == "int":
            p[key] = int(float(s))
        elif kind == "pct":
            p[key] = float(s) / 100.0
        elif kind == "text":
            p[key] = s
        else:
            p[key] = float(s)
    return p


def fmt_num(x, nd=2):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"{x:,.{nd}f}"


def fmt_pct(x, nd=2):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "—"
    return f"{x * 100:,.{nd}f}%"


def dscr_series(m):
    """引擎不单独输出 DSCR 数组，按 CFADS / 还本付息逐年计算。"""
    svc = np.asarray(m["debt_service"], dtype=float)
    cfads = np.asarray(m["cfads"], dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(svc > 1e-9, cfads / svc, np.nan)


def build_extra(m):
    interest_total = np.asarray(m["interest"]) + np.asarray(m["wc_int"])
    tax_surcharge = np.asarray(m["sales_tax"]) + np.asarray(m["surtax"])
    ebit = np.asarray(m["ebit"])
    with np.errstate(divide="ignore", invalid="ignore"):
        icr = np.where(interest_total > 1e-9, ebit / interest_total, np.nan)
    return {
        "interest_total": interest_total,
        "tax_surcharge": tax_surcharge,
        # 「减：可抵扣进项税」列（总成本表用）：取负值，使分项竖加等于成本费用合计；
        # 仅含税情形非零，其余显示为「—」
        "input_vat_ded": np.where(np.asarray(m["input_vat_op"]) > 1e-9,
                                  -np.asarray(m["input_vat_op"]), np.nan),
        # 进项税不构成费用：成本费用合计按不含税经营成本（T-202610-006）
        # 销售税及附加不在成本费用合计内（损益表单列一行，总成本表无税费行）
        "total_cost": (np.asarray(m["opex"]) - np.asarray(m["input_vat_op"])
                       + np.asarray(m["dep"]) + np.asarray(m["amort"])
                       + interest_total),
        "dscr": dscr_series(m),
        "icr": icr,
        "cum_p": np.cumsum(np.asarray(m["cf_project"])),
        "cum_e": np.cumsum(np.asarray(m["cf_equity"])),
        "cum_dep": np.cumsum(np.asarray(m["dep"])),
        "cum_amort": np.cumsum(np.asarray(m["amort"])),
        "dsra_delta": np.asarray(m["dsra_rel"]) - np.asarray(m["dsra_fund"]),
        # C-03① 全投资现金流实际只扣「调整所得税」；预扣税属权益分配环节，
        # 已在 cf_equity 中扣减，不进入全投资口径（见资本金现金流表）。
        "tax_project": -np.asarray(m["tax_unlev"]),
        # C-03② 无形及递延资产单列，与 cf_initial_capex 分项对应；
        # 建设期利息不进全投资现金流（融资成本，见资本金现金流与融资方案）
        "_other_asset": np.asarray([
            -m["p"]["other_asset_base"] / m["t"] if i < m["t"] else 0.0
            for i in range(m["n"])]),
        # 现金流报表的「流出」统一取负值，使 Σ 明细 = 净现金流量（竖加自洽）
        "opex_cf": -np.asarray(m["opex_ex_vat"]),
        "tax_surcharge_cf": -tax_surcharge,
        "local_levy_cf": -np.asarray(m["local_levy"]),
        "principal_cf": -np.asarray(m["principal"]),
        "wc_repay_cf": -np.asarray(m["wc_repay"]),
        "withholding_cf": -np.asarray(m["withholding"]),
        "fund_total": (np.asarray(m["draw"]) + np.asarray(m["wc_draw"])
                       + np.asarray(m["equity_cf"]) * -1
                       + np.asarray([m["p"]["idc"] / m["t"] if i < m["t"] else 0.0
                                     for i in range(m["n"])])),
        "_capex": np.asarray([_capex_invest(m, None, i) for i in range(m["n"])]),
        "_wc": np.asarray([_wc_invest(m, None, i) for i in range(m["n"])]),
        "_salvage": np.asarray([_salvage_rec(m, None, i) for i in range(m["n"])]),
        "_wcrec": np.asarray([_wc_recover(m, None, i) for i in range(m["n"])]),
        "_equityin": np.asarray([_equity_in(m, None, i) for i in range(m["n"])]),
        "_idc": np.asarray([_idc_cap(m, None, i) for i in range(m["n"])]),
        "dep_base": np.full(m["n"], float(m["p"]["dep_base"])),
        "other_asset_base": np.full(m["n"], float(m["p"]["other_asset_base"])),
        "dep_rate": np.full(m["n"], float(m["dep_rate"])),
        "amort_rate": np.full(m["n"], float(m["amort_rate"])),
    }


def resolve_value(m, extra, src, i):
    if callable(src):
        return src(m, extra, i)
    if isinstance(src, tuple):
        return sum(np.asarray(m[s])[i] for s in src)
    if src in extra:
        return np.asarray(extra[src])[i]
    return np.asarray(m[src])[i]


def fmt_cell(v, kind):
    if kind == "op":
        return str(int(v)) if v else "—"
    if kind == "int":
        return str(int(v))
    if v is None or not np.isfinite(float(v)):
        return "—"
    if kind == "f0":
        return f"{v:,.0f}"
    if kind == "f1":
        return f"{v:,.1f}"
    if kind == "f2":
        return f"{v:,.2f}"
    return f"{v:,.4f}"


# ── 决策信息模版 ───────────────────────────────────────────────────────
DECISION_ITEMS = {
    "pv": [
        ("光伏组件", "dt_pv_module"),
        ("汇流箱/箱变", "dt_pv_box"),
        ("逆变器", "dt_pv_inverter"),
        ("支架", "dt_pv_bracket"),
        ("桩基", "dt_pv_pile"),
        ("电缆", "dt_pv_cable"),
        ("通讯监控", "dt_pv_comms"),
        ("设备安装", "dt_pv_install_equip"),
        ("电气安装", "dt_pv_install_elec"),
        ("调试", "dt_pv_debug"),
        ("基础", "dt_pv_foundation"),
        ("围栏", "dt_pv_fence"),
        ("升压站", "dt_pv_booster"),
        ("勘察设计", "dt_pv_survey"),
        ("运输", "dt_pv_freight"),
        ("境内税费", "dt_pv_tax"),
        ("其他", "dt_pv_other"),
    ],
    "wind": [
        ("风电机组", "dt_wind_turbine"),
        ("塔筒", "dt_wind_tower"),
        ("电气设备", "dt_wind_elec"),
        ("土建", "dt_wind_civil"),
        ("安装", "dt_wind_install"),
        ("道路", "dt_wind_road"),
        ("集电线路", "dt_wind_grid"),
        ("吊装", "dt_wind_hoist"),
        ("调试", "dt_wind_commission"),
        ("升压站", "dt_wind_booster"),
        ("勘察设计", "dt_wind_survey"),
        ("运输", "dt_wind_freight"),
        ("境内税费", "dt_wind_tax"),
        ("其他", "dt_wind_other"),
    ],
}


def _row(item, value, unit, note="", cls=""):
    r = {"cells": [bi(item), value, unit, bi(note)]}
    if cls:
        r["cls"] = cls
    return r


def _c(t, span=1, align=None, strong=False, **extra):
    c = {"t": t}
    if span != 1:
        c["span"] = span
    if align:
        c["align"] = align
    if strong:
        c["strong"] = True
    c.update(extra)
    return c


def _dec_items(p, dc):
    """按网页口径：a / b / c … 编号 + 中文/英文两行内容。"""
    rows = []
    for i, (label, key) in enumerate(DECISION_ITEMS[p["gen_type"]]):
        price = float(p[key])
        amt = price * dc * 100.0
        trans = en(label)
        if trans and trans != label:
            label = f"{label} {trans}"
        rows.append((chr(ord("a") + i), label, price, amt, "", key))
    return rows


def build_decision(m, money_scale=1.0, money_unit=None, price_scale=1.0, price_prefix="元"):
    """决策信息模版（网页格式）：1 项目测算情况 / 2 建设期利息和业主管理费 /
    3 前期开发阶段 / 4 EPC总包工程部分；最后一项可调费用按结余为 0 反推。

    money_scale/money_unit 仅供导出：英文/繁体版把「万元」换算成 k（×10）。
    """
    p = m["p"]
    k_unit = money_unit is not None
    unit_cn = money_unit or "万元"

    def mfmt(x):
        return f"{x * money_scale:,.1f}"

    def money_subhead(cn, en_txt, cn_unit="", en_unit=""):
        """k 模式把中英文各自写成带单位的一行，挑行时不丢单位。"""
        if k_unit:
            return (f"{cn}（{unit_cn}{cn_unit}）\n"
                    f"{en_txt} ({unit_cn}{en_unit})")
        return f"{cn}\n{en_txt}\n（{unit_cn}{cn_unit}）"

    met = m["metrics"]
    kind = p["gen_type"]
    t, a = m["t"], m["a"]
    dc = float(p["cap_dc_mw"])
    ac = float(p["cap_ac_mw"])
    kind_cn = "光伏" if kind == "pv" else "风电"
    kind_en = "PV" if kind == "pv" else "Wind"

    total_inv = float(p["total_investment"])
    idc = float(p["idc"])
    omf = float(p["owner_mgmt_fee"])
    wc = float(p["working_capital"])
    financing = 0.0
    es = idc + omf + wc + financing
    predev = float(p.get("predev", 0.0))

    stor = float(p.get("stor_initial_inv", 0.0))
    stor_epc = float(p.get("storage_epc", stor))   # 含各次更换折现现值
    mwh = ac * float(p["storage_ratio"]) * float(p["storage_duration"])
    stor_price = stor / (mwh * 100.0) if mwh else 0.0

    other_key = "dt_pv_other" if kind == "pv" else "dt_wind_other"
    items = [r for r in _dec_items(p, dc) if r[5] != other_key]
    epc_fixed = sum(r[3] for r in items) + stor_epc
    adjustable = total_inv - es - predev - epc_fixed
    epc_total = epc_fixed + adjustable

    def pv(price):
        return f"{price:,.4f}"

    unit_row = (
        "单位：人民币 k · 单价按 元/W（储能 元/Wh）计\n"
        "Unit: k CNY · Prices in CNY/W (storage CNY/Wh)"
    ) if k_unit else (
        "单位：人民币万元 · 单价按 元/W（储能 元/Wh）计\n"
        "Unit: 10K CNY · Prices in CNY/W (storage CNY/Wh)")

    # ── 第 1 块：抬头 + 项目测算情况 ──
    name_cn = str(p.get("project_name") or "").strip() or \
        f"RNE 项目 — {dc:,.0f} MW DC / {ac:,.0f} MW AC {kind_cn}项目"
    name_en = str(p.get("project_name_en") or "").strip() or \
        f"RNE Project — {dc:,.0f} MW DC / {ac:,.0f} MW AC {kind_en} Project"
    b1 = [
        {"cls": "banner", "cells": [_c(
            f"{name_cn} 投资构成情况\n"
            f"{name_en} Investment Composition", span=8)]},
        {"cls": "unit-row", "cells": [_c(unit_row, span=8, align="right")]},
        {"cls": "sect", "cells": [_c(
            "1 项目测算情况\nProject Measurements", span=8)]},
        {"cls": "subhead", "cells": [
            _c("交流/直流容量（MW）容配比\nAC/DC capacity ratio"),
            _c("电价（不含税）\nElectricity Price\n（元/kWh）"),
            _c("首年利用小时\nFirst Year Hours\n（h）"),
            _c("储能比例 / 配置小时数\nStorage Ratio/Duration"),
            _c("DSCR 偿债备付率\n（min/avg）"),
            _c("项目占地\nLand\n（公顷 Hectare）"),
            _c("年租金标准\nAnnual Rent\n（US$/Hectare）"),
            _c(money_subhead("土地补偿", "Land Compensation", "/年", "/yr")),
        ]},
        {"cls": "val", "cells": [
            _c(f"{ac:,.0f} / {dc:,.0f}", align="center"),
            _c(f"{float(p['tariff']):,.4f}", align="center"),
            _c(f"{float(m['hours'][t]):,.0f}", align="center"),
            _c(f"{float(p['storage_ratio']) * 100:.0f}% / "
               f"{float(p['storage_duration']):g}h", align="center"),
            _c(f"{float(met['min_dscr']):,.2f} / {float(met['avg_dscr']):,.2f}",
               align="center"),
            _c(f"{float(p['land_area']):,.1f}", align="center"),
            _c(f"{float(p['land_rent_usd']):,.0f}", align="center"),
            _c(mfmt(float(p['land_comp_annual'])), align="center"),
        ]},
        {"cls": "subhead", "cells": [
            _c(money_subhead("项目总投资", "Total Investment")),
            _c("全投资 IRR\nProject IRR"),
            _c("资本金 IRR\nEquity IRR"),
            _c(money_subhead("其中：电站总投资", "Station Investment")),
            _c(money_subhead("其中：储能总投资", "Storage Investment")),
            _c("储能动态投资造价\nStorage Cost\n（元/Wh）"),
            _c("电站动态投资造价\nStation Cost\n（元/W）"),
            _c("平均运维成本\nAvg O&amp;M Cost\n（元/kW）"),
        ]},
    ]
    # 电站/储能总投资直接取引擎派生值（EPC + 业主管理费），与左栏同口径
    station_inv = float(p["station_invest"])
    avg_om = float(np.mean(m["opex"][t:t + a])) * 1e4 / (dc * 1000.0)
    b1.append({"cls": "val", "cells": [
        _c(mfmt(total_inv), align="center"),
        _c(f"{float(met['project_irr']) * 100:,.2f}%", align="center"),
        _c(f"{float(met['equity_irr']) * 100:,.2f}%", align="center"),
        _c(mfmt(station_inv), align="center"),
        _c(mfmt(float(p["storage_invest"])), align="center"),
        _c(f"{stor_price:,.4f}", align="center"),
        _c(f"{station_inv / (dc * 100):,.2f}", align="center"),
        _c(f"{avg_om:,.2f}", align="center"),
    ]})
    b1.append({"cls": "subtotal", "cells": [
        _c("小计 Subtotal — 项目总投资 Total Investment", span=4, strong=True),
        _c(mfmt(total_inv), span=3, align="right", strong=True,
           pad="calc(11.5% + 6px)", sub="s1"),
        _c("", span=1),
    ]})
    b1.append({"cls": "note-row", "cells": [_c(
        f"测算总投资 Estimated total investment —— 当收益率为 When IRR = "
        f"{float(met['project_irr']) * 100:,.2f}% ，总投资为 Total Investment = "
        f"{mfmt(total_inv)} {unit_cn}", span=8)]})

    # ── 第 2、3、4 块：分项表格 ──
    item_head = [
        _c("编号", align="center"),
        _c("内容 Content"),
        _c(f"单价 Price ({price_prefix}/W · {price_prefix}/Wh)", align="right"),
        _c(money_subhead("金额", "Amount") if k_unit
           else "金额 Amount（万元 / 10K CNY）", align="right"),
        _c("备注 Note", span=2),
    ]

    def sub_row(sec, value, extra=""):
        return {"cls": "subtotal", "cells": [
            _c(""),
            _c("小计 Subtotal", strong=True),
            _c(""),
            _c(mfmt(value), align="right", strong=True, sub=f"s{sec}"),
            _c(extra, span=2),
        ]}

    def bal_row(label, value, extra="", bal=""):
        if bal == "b3" and abs(value) < 0.05:
            value = 0.0
        return {"cls": "balance", "cells": [
            _c(""),
            _c(label, strong=True),
            _c(mfmt(value), align="left", strong=True, bal=bal, span=2),
            _c(extra, span=2),
        ]}

    def item_row(code, label, price, amt, note, sec, price_unit="元/W",
                 unit="W", param=None, role="", readonly=False):
        _p = (price * price_scale) if (price is not None) else None
        if _p is None:
            price_txt = ""
        elif _p == 0:
            price_txt = "—"
        else:
            price_txt = f"{_p:,.4f}"
        shown = label.replace("\n", " ") if label else ""
        return {"cls": "item", "sec": sec, "key": f"{sec}{code}",
                "unit": unit, "param": param or "", "role": role, "cells": [
            _c(code),
            _c(shown) if readonly else _c(shown, input="text", value=shown),
            _c(price_txt, align="right",
               input=(None if (readonly or price_scale != 1.0) else "num"),
               value=("" if _p is None else f"{_p:.6g}")),
            _c(mfmt(amt) if amt is not None else "", align="right",
               amount=True, value=(amt if amt is not None else 0)),
            _c(note, span=2) if readonly else _c(note, span=2, input="text", value=note or ""),
        ]}

    block2 = [{"cls": "sect", "cells": [_c(
        "2 建设期利息和业主管理费\nConstruction Period Interest & Owner Mgmt Fees",
        span=8)]},
        {"cls": "subhead", "cells": item_head},
        item_row("a", "建设期利息 Interest during construction period",
                 idc / (dc * 100), idc, "", 2),
        item_row("b", "业主管理费（含电站+储能）Owner mgmt fee (Station+Storage)",
                 omf / (dc * 100), omf, "", 2),
        item_row("c", "流动资金 Working capital", wc / (dc * 100), wc, "", 2),
        item_row("d", "融资费 Financing fee", 0.0, financing,
                 "本模型未单列 Not modeled", 2),
        item_row("e", "", None, None, "", 2),
        sub_row(2, es),
        bal_row("结余 balance = (1) − (2)", total_inv - es, bal="b1"),
    ]

    block3 = [{"cls": "sect", "cells": [_c(
        "3 前期开发阶段（项目前期开发费）\nPre-development Stage (pre-development cost)", span=8)]},
        {"cls": "subhead", "cells": item_head},
        item_row("a", "项目前期开发费 Pre-development Cost",
                 float(p.get("predev_price_per_w", 0.2)), predev,
                 "引用左侧「项目前期开发费」参数，如需修改请到参数列表 Referenced from the left-hand parameter list",
                 3, price_unit="元/Wp", param="predev_price_per_w", readonly=True),
        item_row("b", "", None, None, "", 3),
        sub_row(3, predev),
        bal_row("结余 balance = (1) − (2) − (3)", total_inv - es - predev,
                bal="b2"),
    ]

    block4 = [{"cls": "sect", "cells": [_c(
        "4 EPC 总包工程部分\nEPC General Contracting", span=8)]},
        {"cls": "subhead", "cells": item_head},
    ]
    for code, label, price, amt, note, key in items:
        block4.append(item_row(code, label, price, amt, note, 4, param=key))
    block4.append(item_row(
        chr(ord("a") + len(items)),
        "储能系统和工程\nEnergy Storage Systems & Engineering",
        stor_price, stor, "", 4, price_unit="元/Wh", unit="Wh"))
    block4.append(item_row(
        chr(ord("a") + len(items) + 1),
        "其他 Others",
        adjustable / (dc * 100) if dc else 0.0, adjustable,
        "按第 3 项结余反推 Back-solved from balance", 4,
        param=other_key, role="adj"))
    block4.append(sub_row(4, epc_total))
    block4.append(bal_row("结余 balance = (1) − (2) − (3) − (4)",
                          total_inv - es - predev - epc_total,
                          f"EPC 造价 Price {epc_total / (dc * 100):,.2f} 元/W",
                          bal="b3"))

    return {"type": "decision",
            "title": f"决策信息模版（{kind_cn}）",
            "title_en": f"Decision Template ({kind_en})",
            "dc_mw": dc,
            "storage_mwh": mwh,
            "total_inv": total_inv,
            "blocks": [b1, block2, block3, block4]}


# ── LCOE 计算表 ────────────────────────────────────────────────────────
def _lcoe_parts(m, rate):
    p = m["p"]
    t, ytot = m["t"], m["ytot"]
    ki = p["tax_rate"]
    fixed = (np.asarray(m["opex"]) + np.asarray(m["sales_tax"])
             + np.asarray(m["surtax"]))[t:]
    shield = (np.asarray(m["dep"]) + np.asarray(m["amort"]))[t:] * ki
    pv_fixed = float(sum(c / (1 + rate) ** i for i, c in enumerate(fixed)))
    pv_shield = float(sum(c / (1 + rate) ** i for i, c in enumerate(shield)))
    pv_salv = float(m["salvage_value"]) / (1 + rate) ** ytot
    pv_gen = float(sum(c / (1 + rate) ** i
                       for i, c in enumerate(np.asarray(m["gen"])[t:] / 1e4)))
    numerator = float(p["total_investment"]) + pv_fixed - pv_shield - pv_salv
    lcoe = numerator / pv_gen / 1e4 if pv_gen > 0 else float("nan")
    return dict(pv_fixed=pv_fixed, pv_shield=pv_shield, pv_salv=pv_salv,
                pv_gen=pv_gen, numerator=numerator, lcoe=lcoe)


def build_lcoe(m, money_scale=1.0, money_unit="万元"):
    """LCOE 计算表。money_scale/money_unit 仅供导出：英文/繁体版把
    「万元」换算成 k（×10）。"""
    p = m["p"]
    r = float(p["discount_rate"])
    q = _lcoe_parts(m, r)

    def mval(x):
        return f"{float(x) * money_scale:,.1f}"

    rows = [
        _row("总投资", mval(p['total_investment']), money_unit, "建设投资 + 建设期利息 + 流动资金"),
        _row("运营成本现值", mval(q['pv_fixed']), money_unit, "经营成本 + 销售税及附加，折现"),
        _row("折旧抵税现值", mval(q['pv_shield']), money_unit, "折旧与摊销 × 所得税率，折现（减项）"),
        _row("残值现值", mval(q['pv_salv']), money_unit, "期末固定资产余值折现（减项）"),
        _row("分子合计", mval(q['numerator']), money_unit, "总投资 + 运营成本现值 − 抵税 − 残值", "total"),
        _row("发电量现值", f"{q['pv_gen']:,.4f}", "亿kWh", "运营期发电量逐年折现"),
        _row("LCOE", f"{q['lcoe']:,.4f}", "元/kWh", "分子合计 ÷ 发电量现值 ÷ 1e4", "total"),
    ]
    return {"type": "def", "title": "LCOE 计算表",
            "title_en": "LCOE Calculation",
            "cols": ["项目", "数值", "单位", "说明"],
            "cols_en": en_list(["项目", "数值", "单位", "说明"]),
            "rows": rows,
            "footer": f"折现率 WACC = {r * 100:.4f}%　｜　折现基准 = 运营第一年　｜　运营期 {m['a']} 年"}


# ── WACC 计算链（网页版口径）──────────────────────────────────────────
def _wacc_core(m, live=None):
    """解析所选国别/行业/币种/Rd 方式，生成单币种与三币种口径。"""
    p = m["p"]
    countries = (live or {}).get("countries") or {}
    country = str(p.get("wacc_country", ""))
    c = countries.get(country) or {}
    rating = str(c.get("rating", "") or "")
    ev = 1.0 - float(p["debt_ratio"])
    dv = float(p["debt_ratio"])
    tc = float(p["tax_rate"])
    bu = float(p["beta_u"])
    bl = float(m["beta_l"])
    erp = float(p["erp"])
    crp = float(p["crp"])
    ds = float(p.get("country_def_spread", 0.0))
    cs = float(p.get("credit_spread", 0.0))
    method = int(p.get("rd_method", 1))
    sel = str(p.get("wacc_ccy", "CNY"))
    local = WD.local_ccy_of(country)
    rf_usd = float(p.get("risk_free_rate_usd", 0.0))
    rf_cny = float(p.get("risk_free_rate_cny", 0.0))
    rf_local = float(p.get("risk_free_rate_local", 0.0))
    rd_inv = float(p["wacc_rd"])

    def rf_of(code):
        if code == "CNY":
            return rf_cny
        if code == "USD":
            return rf_usd
        if code == "LOCAL":
            return rf_local or rf_usd
        if local and code == local:
            return rf_local or rf_usd
        return rf_usd

    def col(code):
        rf = rf_of(code)
        re_ = rf + bl * erp + crp
        rd = (rf + ds + cs) if method == 1 else rd_inv
        return {"rf": rf, "re": re_, "rd": rd, "rd_at": rd * (1 - tc),
                "wacc": ev * re_ + dv * rd * (1 - tc)}

    return {
        "p": p, "ev": ev, "dv": dv, "tc": tc, "bu": bu, "bl": bl,
        "erp": erp, "crp": crp, "ds": ds, "cs": cs, "method": method,
        "country": country, "rating": rating, "sector": str(p.get("wacc_sector", "")),
        "sel": sel, "local": local,
        "other": ("USD" if sel != "USD" else "CNY"),
        "cls": WD.country_class_label(rating),
        "adder": WD.country_class_adder(rating),
        "live": live, "col": col, "rf_of": rf_of, "rd_inv": rd_inv,
    }


def _ccy_disp(code, local):
    if code == "LOCAL":
        info = WD.LOCAL_CCY_DB.get(local)
        return f"本国货币 {info['cn']} {local}" if info else "本国货币 Local"
    if code == "CNY":
        return "人民币 RMB"
    if code == "USD":
        return "美元 USD"
    info = WD.LOCAL_CCY_DB.get(code)
    return f"{info['cn']} {code}" if info else (code or "—")


def _ccy_disp_en(code, local):
    if code == "LOCAL":
        info = WD.LOCAL_CCY_DB.get(local)
        return f"Local {info['en']} {local}" if info else "Local currency"
    if code == "CNY":
        return "Chinese Yuan RMB"
    if code == "USD":
        return "US Dollar USD"
    info = WD.LOCAL_CCY_DB.get(code)
    return f"{info['en']} {code}" if info else (code or "—")


def _live_note(live):
    src = {"live": "联网实时", "cache": "本地快照", "fallback": "内置兜底"}.get(
        (live or {}).get("source"), "内置兜底")
    note = f"取数：Damodaran ctryprem / BetasGlobal · {src}"
    if live and live.get("asof"):
        note += f" · 数据日期 {live['asof']}"
    if live and live.get("fetched_at"):
        note += f" · 抓取 {live['fetched_at'][:16].replace('T', ' ')}"
    return note


def build_wacc(m, live=None):
    c = _wacc_core(m, live)
    p, sel = c["p"], c["sel"]
    cc = c["col"](sel)
    rf = cc["rf"]
    rf_src = {"CNY": "人民币 10 年期国债", "USD": "美元 10 年期国债"}.get(
        sel, f"本国货币 10 年期国债（{c['local'] or '—'}）")
    mode = (f"合成评级法：Rf {rf * 100:,.3f}% ＋ 国别违约利差 {c['ds'] * 100:.2f}%"
            f" ＋ 信用利差 {c['cs'] * 100:.2f}%") if c["method"] == 1 \
        else "投资人指定（模型不另加载国别利差）"
    country_disp = WD.country_label(c["country"]) if c["country"] else "—"
    rows = [
        _row("权益占比 E/V", f"{c['ev'] * 100:,.2f}", "%", "1 − 债务占比"),
        _row("债务占比 D/V", f"{c['dv'] * 100:,.2f}", "%", "债务占比"),
        _row("所得税率 Tc", f"{c['tc'] * 100:,.2f}", "%", ""),
        _row("项目所在国", country_disp, "—",
             f"国别类别 {c['cls']}（信用利差加成 +{c['adder']:.2f}%）"),
        _row("所属行业", c["sector"] or "—", "—", "行业无杠杆贝塔取数口径"),
        _row("无杠杆 βu", f"{c['bu']:,.4f}", "—", "行业无杠杆贝塔"),
        _row("杠杆 βL", f"{c['bl']:,.4f}", "—", "βu × [1 + (1−Tc) × D/E]"),
        _row("WACC 采用币种", _ccy_disp(sel, c["local"]), "—",
             "所选币种的 WACC 即模型折现率"),
        _row("无风险利率 Rf", f"{rf * 100:,.4f}", "%", rf_src),
        _row("股权风险溢价 ERP", f"{c['erp'] * 100:,.4f}", "%", "成熟市场 ERP"),
        _row("国别风险溢价 CRP", f"{c['crp'] * 100:,.4f}", "%",
             f"{c['country']}（{c['rating'] or 'NR'}）"),
        _row("国别违约利差", f"{c['ds'] * 100:,.4f}", "%", "Damodaran ctryprem"),
        _row("信用利差", f"{c['cs'] * 100:,.4f}", "%",
             f"DSCR 档 + 国别类别（{c['cls']} +{c['adder']:.2f}%）"),
        _row("权益成本 Re", f"{cc['re'] * 100:,.4f}", "%", "Rf + βL × ERP + CRP"),
        _row("债务成本 Rd", f"{cc['rd'] * 100:,.4f}", "%", mode),
        _row("税后债务成本", f"{cc['rd_at'] * 100:,.4f}", "%", "Rd × (1 − Tc)"),
        _row("WACC", f"{cc['wacc'] * 100:,.4f}", "%",
             "E/V × Re + D/V × Rd × (1 − Tc)", "total"),
    ]
    footer = (
        f"WACC ＝ (E/V)·Re ＋ (D/V)(1−Tc)·Rd ＝ {c['ev'] * 100:.0f}% × "
        f"{cc['re'] * 100:.4f}% ＋ {c['dv'] * 100:.0f}% × "
        f"{cc['rd'] * 100:.4f}% × (1 − {c['tc'] * 100:.0f}%) ＝ "
        f"{cc['wacc'] * 100:.4f}%　｜　" + _live_note(live))
    return {"type": "def", "title": "WACC 计算表",
            "title_en": "WACC Calculation",
            "cols": ["项目", "数值", "单位", "说明"],
            "cols_en": en_list(["项目", "数值", "单位", "说明"]),
            "rows": rows, "footer": footer}


def build_wacc_compare(m, live=None):
    """三币种口径对照：本模型币种 / 对照币种 / 本国货币。"""
    c = _wacc_core(m, live)
    sel, other, local = c["sel"], c["other"], c["local"]
    cols = ["口径", _ccy_disp(sel, local) + "（本模型）",
            _ccy_disp(other, local) + "（对照）",
            (_ccy_disp(local, local) + "（本国货币）") if local else "—（无本币）"]
    cols_en = ["Suite", _ccy_disp_en(sel, local) + " (model)",
               _ccy_disp_en(other, local) + " (reference)",
               (_ccy_disp_en(local, local) + " (local)") if local else "— (no local ccy)"]
    A = c["col"](sel)
    B = c["col"](other)
    C = c["col"](local) if local else None

    def row(label, key, fmt, strong=False):
        cells = [bi(label), fmt(A[key]), fmt(B[key]),
                 fmt(C[key]) if C else "—"]
        return {"cells": cells, **({"cls": "total"} if strong else {})}

    pct = lambda v: f"{v * 100:,.2f}%"
    rows = [
        row("无风险利率 Rf", "rf", pct),
        {"cells": [bi("再杠杆 βL"), f"{c['bl']:,.4f}", f"{c['bl']:,.4f}",
                   f"{c['bl']:,.4f}"]},
        row("权益成本 Re", "re", pct),
        row("债务成本 Rd", "rd", pct),
        row("税后债务成本 Rd×(1−Tc)", "rd_at", pct),
        row("WACC", "wacc", pct, strong=True),
    ]
    footer = (
        f"βL 与 ERP/CRP 三币种共用；Rf 取各币种 10Y 国债。"
        f"所选币种 WACC = {A['wacc'] * 100:.4f}%（已作为模型折现率）"
        f"；Rd 口径：{'合成评级法' if c['method'] == 1 else '投资人指定'}。"
        f"　｜　{_live_note(live)}")
    return {"type": "matrix", "title": "WACC 三币种对比",
            "title_en": "WACC Currency Comparison",
            "cols": cols, "cols_en": cols_en, "base": 1,
            "rows": rows, "footer": footer}


def build_wacc_sens(m, live=None):
    """Rd × CRP 5×5 敏感性（网页版同款）。"""
    c = _wacc_core(m, live)
    p = c["p"]
    rf = float(p["risk_free_rate"])
    rd_rows = [0.04, 0.06, 0.08, 0.10, 0.12]
    crp_cols = [0.02, 0.04, 0.06, 0.0841, 0.10]
    rd_eff = c["col"](c["sel"])["rd"]

    def nearest(arr, v):
        return min(range(len(arr)), key=lambda i: abs(arr[i] - v))

    base_rd = nearest(rd_rows, rd_eff)
    base_crp = nearest(crp_cols, float(p["crp"]))
    rows = []
    for ri, rd in enumerate(rd_rows):
        cells = [f"{rd * 100:.1f}%"]
        for ci, crp in enumerate(crp_cols):
            re_ = rf + c["bl"] * c["erp"] + crp
            wacc = c["ev"] * re_ + c["dv"] * rd * (1 - c["tc"])
            txt = f"{wacc * 100:,.2f}%"
            if ri == base_rd and ci == base_crp:
                txt += " ★"
            cells.append(txt)
        rows.append({"cells": cells})
    cols = ["Rd ＼ CRP", "2.0%", "4.0%", "6.0%", "8.41%", "10.0%"]
    return {"type": "matrix", "title": "WACC 敏感度",
            "title_en": "WACC Sensitivity (Rd × CRP)",
            "cols": cols, "cols_en": cols,
            "base": base_crp + 1,
            "rows": rows,
            "footer": f"行＝债务成本 Rd，列＝国别风险溢价 CRP；★ 为当前口径"
                      f"（Rd {rd_eff * 100:.2f}% · CRP {float(p['crp']) * 100:.2f}%）"}


def build_wacc_pack(m, live=None):
    """WACC 计算表合集：计算过程 → 三币种对比 → 敏感度（同一页依次排列）。"""
    steps = dict(build_wacc(m, live))
    steps["title"] = "WACC 计算过程"
    steps["title_en"] = "WACC Calculation Steps"
    return {"type": "combo", "title": "WACC计算表", "title_en": "WACC Calculation",
            "sections": [steps, build_wacc_compare(m, live),
                         build_wacc_sens(m, live)]}
