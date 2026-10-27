#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RNE 600MW 光伏 + 储能（吉尔吉斯斯坦）项目财务模型 —— 计算引擎。

纯 Python + numpy，不依赖 Excel。build_ib_model.py 调用本模块得到全部年度数组，
再写入工作簿；本文件也可单独运行以打印基准情形并与原模型对账。

时间轴：项目年 1..n，其中 n = 建设期(construct_period) + 运营期(oper_period)。
       项目年 1..t = 建设期；项目年 t+1..t+a = 运营年 1..a。
单位：万元（另注明者除外）。

设计口径的两处来源：
  · 结构（报表体系、情形开关、LCOE/ICR/CAPM）对齐 yellowfir.com/REmodel.html 网页版；
  · 参数与计税口径以《5美分-吉尔吉斯坦（总投倒算）…Financial Model》的
    「假设及结论」面板为准（SOURCE_PARAMS 列出其取值）。
两者不一致处，DEFAULTS 取源模型口径，并在「对账」页列示差异。
"""
import numpy as np

# ── 基准时间轴（其余情形由 DEFAULTS 覆盖）───────────────────────────────
N_OP = 25
# 项目总年数 = 建设期 + 运营期，由参数动态决定，不设固定网格。
# 建设期 1 年 → 26 列；建设期 2 年 → 27 列；运营期恒为 OperationPeriod 年。

# 源模型《假设及结论》面板的取值，用于对账与差异说明
SOURCE_PARAMS = dict(
    construct_period=1, oper_period=25, cap_ac_mw=100.0, cap_dc_mw=125.0,
    total_investment=268126.0445, fixed_asset_capex=263308.3592,
    idc=3317.6853, working_capital=1500.0, dep_base=266626.0445,
    debt_ratio=0.70, debt_rate=0.036, debt_tenor=10, repay_method=2,
    tax_rate=0.10, tax_holiday_toggle="NO", tax_preference_years=10,
    withholding_rate=0.05, vat_rate=0.12, vat_exempt_years=25, vat_refund="NO",
    sales_tax_rate=0.01, sales_tax_exempt_years=10,
    city_constr_tax=0.0, edu_surcharge=0.0,
    insurance_method=2, insurance_rate=0.005,
    land_area=1232.7, annual_rent=180.0, exchange_rate=6.6913,
    land_compensation=272.0, land_comp_one_off=33.52944,
    land_tax_base=0.0, land_tax_rate=0.01,
    om_cost_mode=0,          # 0 自下而上（默认） 1 投资额×比例（定额）
    om_cost_pct=0.012,       # 投资额比例法的年运维费率
    storage_rev_on=1,        # 1 储能计上网收入（并扣减电站小时） 0 不计
    # 全投资现金流的初始投入＝「建设投资 + 无形及递延资产 + 建设期利息」（2026-10-26 业主定）：
    # 建设期利息按资本化口径计入总投资，全投资现金流以总投资（除流动资金外）为初始流出，
    # 使项目层面与会计口径（IDC 资本化进固定资产、随折旧摊销）保持一致。
    debt_base_mode=0,        # 0 债务基数=折旧基数（可抵押资产） 1 债务基数=项目总投资
    om_mode=1, cost_method=1, warranty_years=0,
    staff_per_50mw=1.3, avg_salary=15.62, benefits_ratio=0.6,
    self_material_in=10.0, self_material_out=10.0,
    self_repair_in=4.0, self_repair_out=9.2,
    storage_staff_per_100mwh=10.0,
    depr_years=25, residual_rate=0.05, reserve_rate=0.10,
    cpi=0.001, decomm_ratio=0.0, sea_area_fee=0.0,
    wc_loan_rate=0.05,             # 短期流贷利率（与 Excel 流动资金借款同率）
    property_tax_base="租赁协议（不计征）",
    equip_price_per_kw=2448.0,
)


DEFAULTS = dict(
    # ── 项目名称（报告/表头用）────────────────────────────────────────
    project_name="吉尔吉斯斯坦共和国100MW光伏发电项目（含储能）",
    project_name_en="Kyrgyzstan 100MW PV Project (with BESS)",
    # ── 情形开关 ───────────────────────────────────────────────────────
    scenario="基准",
    gen_type="pv",                 # pv | wind        —— 发电类型
    plant_type=1,                  # 1 陆上/光伏储能  2 海上
    sea_area_fee=0.0,              # 海域使用金（万元/年，仅海上电站计入）
    construct_period=1,            # 建设期（年）
    oper_period=25,                # 运营期（年）
    tariff_incl_tax=0,             # 电价是否含增值税与销售税（源模型 Q7=NO）
    battery_type="磷酸铁锂",
    om_mode=1,                     # 1 自维  2 外委
    cost_method=1,                 # 1 定额  2 比例  3 仅储能
    tax_holiday_mode=0,            # 0 直接免税 N 年  1 三免三减半
    vat_refund=0,                  # 【保留位·未使用】引擎计算从不引用；
                                   # 口径（留抵退还 50% / 应交减半）待裁定后再接线，
                                   # 勿据此出数（T-202610-006 §vat_refund）
    insurance_method=2,            # 1 固定定额  2 自定比率
    insurance_rate=0.001,          # 自定比率：第 1–5 年费率（即网页版第 1 档）
    ins_rate2=0.002,               # 第 6–10 年
    ins_rate3=0.003,               # 第 11–15 年
    ins_rate4=0.004,               # 第 16–20 年
    ins_rate5=0.005,               # 第 21 年起
    repay_method=1,                # 1 等额本息（委托方口径）  2 等额本金
    om_block_rates=None,           # 比例法维修费率（每 5 年一档）；None=按发电类型取默认

    # ── 容量与发电 ────────────────────────────────────────────────────
    start_year=2027,
    cap_ac_mw=100.0,
    cap_dc_mw=125.0,
    nameplate_hours=1545.0,
    actual_gen_hours=1542.0,     # 首年可用小时（唯一入口；原「铭牌利用小时」已并入此项）
    line_loss=0.0,                 # 线损率
    op_hours_y1=1424.55,           # 首年等效利用小时（基准口径）
    guaranteed_hours_policy=1550.0,  # 政策性保障小时数
    market_trade_hours=0.0,   # 市场化交易小时数
    overgen_hours=0.0,        # 超发小时数
    first_year_haircut=0.01,
    annual_degradation=0.004,

    # ── 电价（分档）──────────────────────────────────────────────────
    tariff=0.35,                   # 保障收购电价
    benchmark_tariff=0.4015,
    subsidy_price=0.0,
    subsidy_years=25,
    guarantee_discount=0.0,
    market_price=0.4015,             # 市场化交易电价
    overgen_price=0.4015,            # 超发电价
    storage_elec_price=0.0,     # 0 = 跟随保障收购（实际上网）电价       # 储能上网电价
    grid_fee=0.0,                  # 过网费（元/kWh，自保障电价扣除）
    ancillary_fee=0.0,             # 辅助服务费（元/kWh，自保障电价扣除）

    # ── 储能 ─────────────────────────────────────────────────────────
    # 储能接入位置：1=发电侧（不算储能收益，全部小时并入电站电量）；2=电网侧（电站扣储能小时，储能单独计收入）
    storage_side=2,   # 已废弃：收入不再区分发电侧/电网侧，保留仅为旧记录兼容
    storage_ratio=0.15,
    storage_avail=1.0,      # 已从界面移除；容量不再打折（旧记录若存 0.85 仍生效）
    storage_duration=4.0,
    storage_hours=350.0,
    storage_days=350.0,
    storage_usable_hours=6000.0,
    storage_efficiency=1.0,   # 已从界面移除：成本容量基数按 100% 计（旧记录若存 0.85 仍生效）
    storage_lease_ratio=1.0,  # 已从界面移除；租赁收入公式不再使用本项
    storage_lease_price=0.0,   # 默认 0（用户口径）；需要租赁收入时手工填
    predev_price_per_w=0.2,    # 项目前期开发费（元/Wp），计入建设投资   # 电网侧默认租赁电价（元/kWh）；发电侧强制按 0 处理
    storage_unit_price=0.5,        # 元/Wh
    replace_cost=0.5,              # 元/Wh，到期更换（用户 2026-10-23 定 0.5，按 app 口径计入基准）
    storage_staff_per_100mwh=0.0,  # 源模型未计入储能运维人员
    storage_outsource_per_100mw=0.0,
    storage_mgmt_rate=0.029,   # 已废弃：统一用 owner_mgmt_rate_stor（储能建设管理费率）
    # 储能运维明细（网页版口径：元/MWh 或 元/kW）
    storage_self_mat_in=0.0, storage_self_mat_out=0.0,
    storage_self_rep_in=0.0, storage_self_rep_out=0.0,
    storage_out_mat_in=0.0, storage_out_mat_out=0.0,
    storage_out_rep_in=0.0, storage_out_rep_out=0.0,
    storage_self_other_in=0.0, storage_self_other_out=0.0,
    storage_out_other_in=0.0, storage_out_other_out=0.0,

    # ── 投资 ─────────────────────────────────────────────────────────
    # 以下四个为《假设》表中作活公式的派生量：基准值由下方驱动量推出（见
    # _derive_params）。它们仍保留在 DEFAULTS 中，以便情形预设直接指定。
    total_investment=268126.0445,
    fixed_asset_capex=263308.3592,
    idc=3317.6853,
    working_capital=1500.0,
    dep_base=266626.0445,
    debt_ratio=0.70,
    other_asset_base=0.0,          # 无形及递延资产原值（摊销基数）
    other_asset_life=10,           # 摊销年限
    # 驱动量：改这些即经 _derive_params 逐级传导
    capex_per_kw=3510.7781226667,  # 单位千瓦建设投资（元/kW，直流）
    wc_per_kw=20.0,                # 流动资金（元/kW，直流）
    epce_station=247200.0,         # 电站 EPC 总价（由单价×直流容量派生）
    epc_price_station=2.8976,       # 电站 EPC 单价（元/W，直流侧）
    owner_mgmt_rate_stn=0.018,     # 业主建设管理费率（电站 EPC）
    station_mgmt_rate=0.018,       # 已废弃：统一用 owner_mgmt_rate_stn（电站建设管理费率）
    owner_mgmt_rate_stor=0.029,    # 业主建设管理费率（储能 EPC）

    # ── 折旧 ─────────────────────────────────────────────────────────
    dep_life=20,
    salvage_rate=0.05,
    equip_price_per_kw=2448.0,     # 备查·不参与计算（与网页版一致，见 A-25）

    # ── 运营成本 ─────────────────────────────────────────────────────
    payroll=499.84,
    maint_y1=690.69,
    material_y1=750.75,
    insurance_base=266626.0445,
    insurance_fixed_rate=0.005,
    land_rent=155.3202,
    land_comp_annual=0.0,          # 逐年土地补偿（源模型为一次性 33.53 万元）
    land_tax=0.0,
    property_tax_rate=0.0,         # 源模型税基为"租赁协议"，不计征
    property_tax_base=266626.0445,
    storage_opex=0.0,
    other_y1=638.1375,
    cpi=0.001,
    # 定额/比例模式参数（元/kW）
    om_self_mat_in=10.0, om_self_mat_out=10.0,
    om_self_rep_in=4.0, om_self_rep_out=9.2,
    om_out_mat_in=0.225, om_out_mat_out=0.47,
    om_out_rep_in=0.262, om_out_rep_out=2.081,
    om_self_other_in=0.0, om_self_other_out=0.0,
    om_out_other_in=0.0, om_out_other_out=0.0,
    # 比例法维修费率（按质保期内外取值；om_block_rates 显式给出时优先）
    self_rep_rate_in=0.003, self_rep_rate_out=0.007,
    out_rep_rate_in=0.015, out_rep_rate_out=0.025,
    om_out_annual=0.0,
    warranty_years=0,
    # ── 口径开关（对齐 I-202610-007 100MW 融资测算）──────────────────
    om_cost_mode=1,        # 0 自下而上分项  1 投资额×比例（定额，委托方口径）
    om_cost_pct=0.012,     # 投资额比例法的年运维费率
    storage_rev_on=1,      # 1 储能计上网收入（并扣减电站小时，app 口径） 0 不计（委托方口径）
    debt_base_mode=0,      # 0 债务基数=折旧基数（建设投资+IDC，财务口径） 1 =项目总投资
    staff_per_50mw=1.3, outsource_per_50mw=1.0,
    avg_salary=15.62, benefits_ratio=0.6,
    land_area=1232.7,              # 项目占地（公顷）
    land_rent_usd=180.0,           # 年租金标准（美元/公顷）
    land_compensation=0.0,         # 征地补偿（美元/公顷·年；>0 时覆盖 land_comp_annual）
    land_tax_rate=0.0,             # 土地税率
    land_tax_base=0.0,             # 土地税计税基础（元/平方米；>0 时覆盖 land_tax）
    exchange_rate=7.0,             # US$ / ¥
    other_cost_rate=8.5,           # 其他费用（元/kW，质保期外）

    # ── 债务 ─────────────────────────────────────────────────────────
    debt_rate=0.07,
    debt_tenor=10,
    dsra_months=0.0,               # 委托方口径未设 DSRA（原 6 个月）
    wc_loan_rate=0.05,          # 与 Excel「流动资金贷款利率」(假设!N30) 一致
    wc_loan_ratio=0.7,             # 流动资金借款占比（短期循环贷，期末还本）

    # ── 税务 ─────────────────────────────────────────────────────────
    tax_rate=0.10,
    tax_holiday_years=10,
    tax_preference_years=10,
    withholding_rate=0.05,         # 按 app 口径计预提/分红税
    reserve_rate=0.0,              # 法定盈余公积金比例（源模型 0.10）
    vat_rate=0.12,
    vat_exempt_years=25,    # 吉尔吉斯 100MW：整个运营期不适用增值税
    sales_tax_rate=0.01,           # 销售税 1%（仅在「电价含税」时缴纳，并参与含税价还原）
    sales_tax_exempt_years=0,      # 源模型 10
    local_levy_mode=0,             # 其他特别费用方式：0=按发电收入百分比  1=固定金额（万元/年）
    local_levy_amount=0.0,         # 其他特别费用固定金额（万元/年，仅 mode=1 生效）
    local_levy_rate=0.01,          # 其他特别费用（按发电收入计，**手动填写**：
                                   # 项目投资协议有约定时填对应比例，无约定填 0；与销售税是两笔）
    city_constr_tax=0.0,
    edu_surcharge=0.0,
    decomm_ratio=0.0,              # 到期拆除费比例（× 固定资产原值，计入最后运营年）

    # ── 回报 ─────────────────────────────────────────────────────────
    discount_rate=0.061224,
    # CAPM / WACC（网页版口径；折现率即由此反算，见 _derive_params）
    # wacc_ccy 决定取哪一币种的 10Y 无风险利率，所选币种的 WACC 即模型折现率
    beta_u=0.55, risk_free_rate=0.01679, erp=0.0423, crp=0.0841,
    wacc_rd=0.0995, country_def_spread=0.0552, credit_spread=0.0275,
    wacc_dscr=1.836,           # 信用利差用 DSCR（与 Excel WACC 表 C48 一致，2026-10-26）
    risk_free_rate_usd=0.0524, risk_free_rate_cny=0.01679, risk_free_rate_local=0.16,
    wacc_country="Kyrgyzstan", wacc_sector="Green & Renewable Energy",
    wacc_ccy="CNY", rd_method=1,

    # ── 决策信息模版分项单价（元/W；金额 = 单价 × 直流装机 × 100 万元）──
    # 光伏
    dt_pv_module=0.800, dt_pv_box=0.100, dt_pv_inverter=0.110,
    dt_pv_bracket=0.130, dt_pv_pile=0.090, dt_pv_cable=0.200,
    dt_pv_comms=0.010, dt_pv_install_equip=0.145, dt_pv_install_elec=0.100,
    dt_pv_debug=0.005, dt_pv_foundation=0.008, dt_pv_fence=0.008,
    dt_pv_booster=0.346, dt_pv_survey=0.050, dt_pv_freight=0.200,
    dt_pv_tax=0.047, dt_pv_other=0.034,
    # 风电
    dt_wind_turbine=1.900, dt_wind_tower=0.250, dt_wind_elec=0.400,
    dt_wind_civil=0.420, dt_wind_install=0.210, dt_wind_road=0.150,
    dt_wind_grid=0.100, dt_wind_hoist=0.350, dt_wind_commission=0.183,
    dt_wind_booster=0.220, dt_wind_survey=0.075, dt_wind_freight=0.250,
    dt_wind_tax=0.040, dt_wind_other=0.034,
)


def _om_unit_rate(p, kind):
    """自维/外委 × 质保期内外，取单位费率（元/kW）。kind: "rep" | "mat"。"""
    pre = "om_self_" if int(p["om_mode"]) == 1 else "om_out_"
    suf = "_in" if float(p["warranty_years"]) >= 1 else "_out"
    return p[pre + kind + suf]


def _derive_params(p, given=None):
    """把《假设》表中的派生量按活公式链在引擎侧同样实现。

    这些量在源模型与工作簿中均为**公式**，不是可填入的输入。因此此处一律由驱动
    量重算，**不接受被覆写**——否则引擎缓存会与工作簿的活公式算出两个数（曾出现
    的情形：overrides 给了 total_investment=290000，而工作簿公式按
    FixedAssetCapex+IDC+WorkingCapital 算得 290091，两侧对不上）。

    要改变这些量，只能改其驱动量（如 单位造价 CapexPerKw、交流容量 CapDC、
    债务比例 DebtRatio）——与在 Excel 里改单元格的行为完全一致。
    工作簿侧的对应公式见 build_ib_model.build_assumptions 的 computed 表。
    """
    def d(key, fn):
        p[key] = fn()

    # 折现率（网页版 CAPM：Hamada 杠杆化 βu → Re → WACC）
    # ① 无风险利率随所选币种取数（人民币/美元/本国货币）
    _ccy = str(p.get("wacc_ccy") or "CNY")
    if _ccy == "USD":
        p["risk_free_rate"] = p.get("risk_free_rate_usd", p["risk_free_rate"])
    elif _ccy == "LOCAL":
        p["risk_free_rate"] = (p.get("risk_free_rate_local")
                               or p.get("risk_free_rate_usd", p["risk_free_rate"]))
    else:
        p["risk_free_rate"] = p.get("risk_free_rate_cny", p["risk_free_rate"])
    # ② Rd：合成评级法 = 无风险利率 + 国别违约利差 + 信用利差；否则投资人指定
    if int(p.get("rd_method", 1)) == 1:
        p["wacc_rd"] = (p["risk_free_rate"] + p.get("country_def_spread", 0.0)
                        + p.get("credit_spread", 0.0))
    d("beta_l", lambda: p["beta_u"] * (1.0 + (1.0 - p["tax_rate"])
                                       * p["debt_ratio"] / (1.0 - p["debt_ratio"])))
    d("cost_equity", lambda: p["risk_free_rate"] + p["beta_l"] * p["erp"] + p["crp"])
    d("discount_rate", lambda: (1.0 - p["debt_ratio"]) * p["cost_equity"]
                              + p["debt_ratio"] * p["wacc_rd"] * (1.0 - p["tax_rate"]))
    # 电量与电价
    d("storage_hours", lambda: p["storage_days"] * p["storage_duration"])
    # 储能投资链（源《假设及结论》B18/E15/L18/M18/J18 的等价式）
    _ac = p["cap_ac_mw"] / 10.0
    d("stor_replace_unit", lambda: _ac * p["replace_cost"] * p["storage_duration"]
                                  * p["storage_ratio"] * 1000.0)
    d("stor_replace_count", lambda: float(p["oper_period"]) / (
        p["storage_usable_hours"] / p["storage_hours"]))
    d("stor_replace_pv", lambda: (
        p["stor_replace_unit"] * np.trunc(p["stor_replace_count"])
        / (1.0 + p["discount_rate"]) ** (p["storage_usable_hours"] / p["storage_hours"])
        + p["stor_replace_unit"] * (np.trunc(p["stor_replace_count"]) - 1.0)
        / (1.0 + p["discount_rate"]) ** p["oper_period"]) if p["storage_duration"] else 0.0)
    # 注：epce_storage / owner_mgmt_fee 已在上方"投资与融资链"按电站/储能分块定义
    # 投资与融资链 —— 电站 / 储能分开：各自 EPC 总价 + 业主管理费 = 各自总投资
    #  ｜ 电站：EPC 总价（输入）× (1 + 建设管理费率)
    #  ｜ 储能：EPC = 交流容量 × 单价 × 时长 × 比例，再 × (1 + 储能管理费率)
    #  ｜ 建设投资合计 = 电站总投资 + 储能总投资
    _ac0 = p["cap_ac_mw"] / 10.0
    d("stor_initial_inv", lambda: _ac0 * p["storage_unit_price"] * p["storage_duration"]
                                 * p["storage_ratio"] * 1000.0)
    d("epce_station", lambda: p["cap_dc_mw"] * p["epc_price_station"] * 100.0)
    d("station_mgmt_fee", lambda: p["epce_station"] * p["owner_mgmt_rate_stn"])
    d("station_invest", lambda: p["epce_station"] + p["station_mgmt_fee"])
    # 储能 EPC 总价 = 初始投资（不含后续更换）
    d("storage_epc", lambda: p["stor_initial_inv"])
    d("storage_mgmt_fee", lambda: p["storage_epc"] * p["owner_mgmt_rate_stor"])
    # 初始总投资 = EPC 总价 + 管理费
    d("storage_initial_invest", lambda: p["storage_epc"] + p["storage_mgmt_fee"])
    # 储能总投资 = 初始总投资 + 各次更换电池投资按 WACC 折现现值
    d("storage_invest", lambda: p["storage_initial_invest"] + p["stor_replace_pv"])
    d("epce_storage", lambda: p["storage_epc"])              # 兼容旧键：储能 EPC
    d("owner_mgmt_fee", lambda: p["station_mgmt_fee"] + p["storage_mgmt_fee"])
    d("predev", lambda: p["predev_price_per_w"] * p["cap_dc_mw"] * 100.0)
    # 项目前期开发费计入建设投资（因此进入总投资、折旧基数）
    d("fixed_asset_capex", lambda: p["station_invest"] + p["storage_initial_invest"] + p["predev"])
    # 单位建设投资已改为**派生量**（由 EPC 反算，不再是输入）
    d("capex_per_kw", lambda: (p["fixed_asset_capex"] * 10.0 / p["cap_dc_mw"])
                              if p["cap_dc_mw"] else 0.0)
    d("working_capital", lambda: p["cap_dc_mw"] * p["wc_per_kw"] / 10.0)
    d("idc", lambda: p["fixed_asset_capex"] * p["debt_ratio"] * p["debt_rate"]
                    * int(p["construct_period"]) / 2.0)
    # EPC 价为含税价 → 价税分离：进项税形成待抵扣，固定资产原值按不含税计
    d("epc_vat_incl", lambda: p["epce_station"] + p["storage_epc"])
    d("input_vat_capex", lambda: (p["epc_vat_incl"] * p["vat_rate"] / (1.0 + p["vat_rate"]))
                              if int(p.get("tariff_incl_tax", 0)) else 0.0)
    d("fixed_asset_ex_vat", lambda: p["fixed_asset_capex"] - p["input_vat_capex"])
    d("dep_base", lambda: p["fixed_asset_ex_vat"] + p["idc"])
    # A-20 无形及递延资产原值另计为投资（由权益/债务筹措，随摊销转入费用）；
    # 原实现只摊不投入 ⇒ 资产无资金来源，BS 恒差一个原值（默认 0 时不可见）。
    d("total_investment", lambda: p["fixed_asset_capex"] + p["idc"] + p["working_capital"]
                               + p["other_asset_base"])
    # 全投资现金流初始投入：建设投资 + 无形及递延资产（建设期利息在 cf_project 中另加，见 DEFAULTS 注释）
    d("cf_initial_capex", lambda: p["fixed_asset_capex"] + p["other_asset_base"])
    d("debt_base_amt", lambda: p["total_investment"]
      if int(p.get("debt_base_mode", 0)) == 1 else p["dep_base"])
    d("insurance_base", lambda: p["dep_base"])
    d("property_tax_base", lambda: p["dep_base"])
    d("equity_ratio", lambda: 1.0 - p["debt_ratio"])
    # 电量与电价
    # 首年发电小时；若留空/填 0，回落到内置 1545 h，避免整表归零
    d("op_hours_y1", lambda: float(p["actual_gen_hours"])
                            if float(p["actual_gen_hours"] or 0) > 0
                            else float(DEFAULTS["actual_gen_hours"]))
    # 运营成本
    d("staff_count", lambda: float(int(p["staff_per_50mw"] * p["cap_dc_mw"] / 50.0 + 0.5)))
    d("payroll", lambda: p["staff_count"] * p["avg_salary"] * (1.0 + p["benefits_ratio"]))
    d("land_rent", lambda: p["land_area"] * p["land_rent_usd"] * p["exchange_rate"] / 1e4)
    d("land_comp_annual", lambda: (
        p["land_area"] * p["land_compensation"] * p["exchange_rate"] / 1e4
        if float(p.get("land_compensation") or 0.0) else p["land_comp_annual"]))
    d("land_tax", lambda: (
        p["land_area"] * p["land_tax_base"] * p["land_tax_rate"]
        if float(p.get("land_tax_base") or 0.0) else p["land_tax"]))
    d("other_y1", lambda: p["other_cost_rate"] * p["cap_dc_mw"] / 10.0 * (1.0 + p["cpi"]))
    d("maint_y1", lambda: _om_unit_rate(p, "rep") * p["cap_dc_mw"] / 10.0 * (1.0 + p["cpi"]))
    d("material_y1", lambda: _om_unit_rate(p, "mat") * p["cap_dc_mw"] / 10.0 * (1.0 + p["cpi"]))


def mirr(cfs, finance, reinvest):
    """修正内部收益率：负流按 finance 折现，正流按 reinvest 复利到期末。"""
    a = np.asarray(cfs, dtype=float)
    n = len(a)
    if n < 2:
        return float("nan")
    pos = [(i, c) for i, c in enumerate(a) if c > 0]
    neg = [(i, c) for i, c in enumerate(a) if c < 0]
    if not pos or not neg:
        return float("nan")
    fv = sum(c * (1.0 + reinvest) ** (n - 1 - i) for i, c in pos)
    pv = sum(c / (1.0 + finance) ** i for i, c in neg)
    if pv >= 0:
        return float("nan")
    return (fv / -pv) ** (1.0 / (n - 1)) - 1.0


def irr(cfs, lo=-0.95, hi=10.0, tol=1e-10):
    """二分法求 IRR；无解返回 nan。"""
    def npv(r):
        return sum(c / (1.0 + r) ** i for i, c in enumerate(cfs))
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return float("nan")
    for _ in range(300):
        mid = (lo + hi) / 2.0
        f_mid = npv(mid)
        if abs(f_mid) < tol:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def npv(rate, cfs, t0=0):
    return sum(c / (1.0 + rate) ** (i + t0) for i, c in enumerate(cfs))


def payback(cfs):
    """静态回收期（累计现金流首次转正的线性插值），年。

    cfs[0] = 项目年 1。若累计值在 0 基下标 i 处首次非负，说明第 i 个运营整年
    （项目年 i）结束时仍为负、项目年第 i+1 年内转正，故回收期 = i + |cum[i-1]|/cf[i]。
    """
    cum = 0.0
    for i, c in enumerate(cfs):
        prev = cum
        cum += c
        if cum >= 0 and i > 0:
            if c == 0:
                return float(i)
            return i + (-prev) / c
    return float("nan")


def annuity_principal(balance, rate, n):
    """等额本息年还款额。"""
    if rate <= 0:
        return balance / n
    return balance * rate * (1 + rate) ** n / ((1 + rate) ** n - 1)


def build_timeline(p, n, a):
    """固定网格上的标志位：建设期为第 1..t 年，运营期为第 t+1..t+a 年，
    网格末端的空档年既非建设期亦非运营期（各年度数组在该处为 0）。"""
    yr = np.arange(1, n + 1)
    t = int(p["construct_period"])
    is_constr = yr <= t
    is_op = (yr > t) & (yr <= t + a)
    k = np.where(is_op, yr - t, 0)
    return yr, is_constr, is_op, k


def compute(**overrides):
    p = dict(DEFAULTS)
    p.update(overrides)
    _derive_params(p)

    t = int(p["construct_period"])
    a = int(p["oper_period"])
    n = t + a                        # 项目总年数 = 建设期 + 运营期（动态，无固定网格）
    last = t + a - 1                 # 末个运营年的列下标
    ytot = t + a                     # 项目总年数（活口径，供折现指数等使用）
    yr, is_constr, is_op, k = build_timeline(p, n, a)

    out = {"p": p, "yr": yr, "n": n, "t": t, "a": a, "last": last, "ytot": ytot,
           "is_constr": is_constr, "is_op": is_op, "k": k}

    # ── 等效利用小时 & 发电量 ─────────────────────────────────────────
    h1 = p["op_hours_y1"]
    # 线损在分档之后统一施加到各档小时（保障/市场化/超发/储能），
    # 这样「保障收购小时 = (发电−储能−市场化−超发)×(1−线损)」与引擎口径一致
    _loss = 1.0 - float(p["line_loss"])

    # ── 小时分档（统一口径，不区分储能接入位置）────────────────────────
    #   储能等效小时 = 配置比例 × 年充放天数 × 储能时长（各年相同）
    #   保障收购小时 = 当年发电小时 − 储能等效小时 − 市场化交易小时 − 超发小时
    kw = p["cap_dc_mw"] * 1000.0                       # kW（直流，电站发电量用）
    kw_ac = p["cap_ac_mw"] * 1000.0                    # kW（交流，储能上网电量用）
    stor_eq = float(p["storage_ratio"] * p["storage_days"] * p["storage_duration"])
    mkt_h = float(p.get("market_trade_hours") or 0.0)
    over_h = float(p.get("overgen_hours") or 0.0)

    # 储能是否计上网收入：0 → 储能不计电量收入，且不从电站发电小时中扣减
    _stor_on = int(p.get("storage_rev_on", 1)) == 1
    _stor_h = stor_eq if _stor_on else 0.0
    h_stor = np.where(is_op, _stor_h * _loss, 0.0)
    h_mkt = np.where(is_op, mkt_h * _loss, 0.0)
    h_over = np.where(is_op, over_h * _loss, 0.0)
    # 衰减只作用于电站自身可用小时（首年＝发电小时−储能−市场化−超发），
    # 储能/市场化/超发小时各按自身基准、不参与衰减（与 Excel 口径一致）
    _plant_base = float(np.maximum(0.0, h1 - _stor_h - mkt_h - over_h))
    hours_plant = np.where(
        is_op,
        np.where(k == 1, _plant_base,
                 _plant_base * (1 - p["first_year_haircut"])
                 - p["annual_degradation"] * _plant_base * (k - 2)),
        0.0)
    hours = np.where(is_op, hours_plant + _stor_h + mkt_h + over_h, 0.0)
    h_guar = hours_plant * _loss

    gen_guar = h_guar * kw / 1e4                       # 万kWh
    gen_mkt = h_mkt * kw / 1e4
    gen_over = h_over * kw / 1e4
    gen_storage = h_stor * kw_ac / 1e4                 # 储能上网电量按交流容量计
    h_plant = h_guar + h_mkt + h_over
    gen_plant = gen_guar + gen_mkt + gen_over          # 电站上网电量（不含储能）
    gen = gen_plant + gen_storage                       # 合计

    # 电价（含税口径下先按含税价计收入，再剥离销项税）
    tax_gross = 1 + p["vat_rate"] + p["sales_tax_rate"] if p["tariff_incl_tax"] else 1.0
    def px(x):
        return x / tax_gross if p["tariff_incl_tax"] else x

    # 保障收购电价（实际上网电价）=（PPA − 过网费 − 辅助服务费）×（1 − 保障电价折让）
    # 补贴年限内另加「差价补贴单价」（默认 0）
    _net = p["benchmark_tariff"] - p["grid_fee"] - p["ancillary_fee"]
    p_guar = np.where(
        k > p["subsidy_years"], px(_net),
        px(_net * (1 - p["guarantee_discount"]) + p["subsidy_price"]))
    p_over, p_mkt = px(p["overgen_price"]), px(p["market_price"])
    # 储能上网电价：填正数用它；留空/0 → 跟随保障收购电价（实际上网电价）
    if float(p.get("storage_elec_price") or 0.0) > 0:
        p_stor = np.where(k > p["subsidy_years"], px(p["benchmark_tariff"]),
                          px(p["storage_elec_price"]))
    else:
        p_stor = p_guar

    rev_guaranteed = np.where(is_op, gen_guar * p_guar, 0.0)
    # 其中：差价补贴收入（已含在保障收购电价内，单列仅为披露，不重复计入收入合计）
    rev_subsidy = np.where(is_op & (k <= p["subsidy_years"]),
                           gen_guar * px(p["subsidy_price"]), 0.0)
    rev_market = np.where(is_op, gen_mkt * p_mkt, 0.0)
    rev_overgen = np.where(is_op, gen_over * p_over, 0.0)
    rev_storage_gen = np.where(is_op, gen_storage * p_stor, 0.0)

    # 储能租赁收入 = DC 容量 × 配置比例 × 储能时长 × 租赁价格（不含年充放天数）
    gen_lease = np.where(is_op, kw_ac * p["storage_ratio"] * p["storage_duration"] / 1e4, 0.0)
    rev_storage_lease = np.where(is_op, gen_lease * p["storage_lease_price"], 0.0)

    # 储能容量/电量（供表格与运维成本使用；不参与收入计算）
    stor_cap = p["cap_dc_mw"] * p["storage_ratio"] * p["storage_avail"]      # MW
    stor_energy = np.where(
        is_op,
        np.where(k == 1, stor_cap,
                 stor_cap * (1 - p["first_year_haircut"])
                 - p["annual_degradation"] * stor_cap * (k - 2)),
        0.0)
    stor_mwh = p["cap_ac_mw"] * p["storage_ratio"] * p["storage_efficiency"] * p["storage_duration"]

    revenue = rev_guaranteed + rev_overgen + rev_market + rev_storage_gen + rev_storage_lease
    # 增值税率系数：三免三减半 → 前 3 年免、4–6 年减半、第 7 年起全额；
    # 直接免税模式 → 按「增值税免税年限」
    if int(p.get("tax_holiday_mode", 0)) == 1:
        _vf = np.where(k <= 3, 0.0, np.where(k <= 6, 0.5, 1.0))
    else:
        _vf = np.where(k <= p["vat_exempt_years"], 0.0, 1.0)
    _vf = np.where(is_op, _vf, 0.0)
    # 销项税 = 不含税收入 × 增值税率 × 系数
    output_vat = (revenue * p["vat_rate"] * _vf
                  if int(p.get("tariff_incl_tax", 0)) else np.zeros(n))
    # 销售税：只有「电价含税」时才缴（它已含在含税价内，价税分离后再计缴）
    sales_tax = np.where(is_op & (k > p["sales_tax_exempt_years"])
                         & (int(p.get("tariff_incl_tax", 0)) == 1),
                         revenue * p["sales_tax_rate"], 0.0)
    # 地方提留：按发电收入 1% 恒缴，与销售税相互独立、不相抵扣
    # 其他特别费用：按发电收入百分比，或固定金额（万元/年）——手动填写，协议无约定填 0
    if int(p.get("local_levy_mode", 0)) == 1:
        local_levy = np.where(is_op, float(p.get("local_levy_amount", 0.0)), 0.0)
    else:
        local_levy = np.where(is_op, revenue * p.get("local_levy_rate", 0.0), 0.0)
    # 附加税在增值税计算后得出（见下）
    surtax = np.zeros(n)

    out.update(hours=hours, gen=gen, gen_plant=gen_plant, gen_guar=gen_guar, gen_over=gen_over,
               gen_mkt=gen_mkt, gen_storage=gen_storage, gen_lease=gen_lease,
               h_guar=h_guar, h_over=h_over, h_mkt=h_mkt, h_storage=h_stor, h_plant=h_plant,
               stor_eq_hours=stor_eq,
               p_guar=p_guar, p_over=p_over, p_mkt=p_mkt, tax_gross=tax_gross,
               rev_guaranteed=rev_guaranteed, rev_subsidy=rev_subsidy,
               rev_overgen=rev_overgen,
               rev_market=rev_market, rev_storage_gen=rev_storage_gen,
               rev_storage_lease=rev_storage_lease,
               stor_cap=stor_cap, stor_energy=stor_energy, stor_mwh=stor_mwh,
               rev_storage=rev_storage_gen + rev_storage_lease,
               revenue=revenue, output_vat=output_vat,
               # 含税收入 = 不含税收入 ×（1 + 增值税率 + 销售税率）
               revenue_incl=revenue + output_vat + sales_tax,
               sales_tax=sales_tax, local_levy=local_levy, surtax=surtax)

    # ── 折旧与摊销（先于运营成本计算，供保险费与比例法维修费取固定资产净值）
    dep_rate = (1 - p["salvage_rate"]) / p["dep_life"]
    dep = np.where(is_op & (k <= p["dep_life"]), p["dep_base"] * dep_rate, 0.0)
    nbv = np.zeros(n)
    nbv[0] = p["dep_base"]
    for i in range(1, n):
        nbv[i] = nbv[i - 1] - dep[i]
    # 期末按账面净值处置固定资产，不产生处置损益；故残值 = 末个运营年的账面净值
    # （固定网格末端可能有空档年，须按运营期末取值）。运营期 = 折旧年限时退化为原值 × 残值率。
    salvage_value = float(nbv[last])

    amort_rate = 1.0 / p["other_asset_life"] if p["other_asset_life"] else 0.0
    amort = np.where(is_op & (k <= p["other_asset_life"]),
                     p["other_asset_base"] * amort_rate, 0.0)
    out.update(dep_rate=dep_rate, dep=dep, nbv=nbv, salvage_value=salvage_value,
               amort_rate=amort_rate, amort=amort)

    # ── 运营成本 ───────────────────────────────────────────────────────
    esc = np.where(is_op, (1 + p["cpi"]) ** np.maximum(k - 1, 0), 0.0)
    payroll = np.where(is_op, p["payroll"], 0.0)

    # 比例法维修费率：每 5 年一档，光伏较风电多一档（与网页版一致）
    om_blocks = p.get("om_block_rates") or (
        [0.001, 0.0025, 0.003, 0.0035, 0.0035] if p["gen_type"] == "pv"
        else [0.001, 0.0025, 0.003, 0.0035])

    # 自维/外委 × 质保期内外，取不同的材料费与维修费率
    in_w = k <= p["warranty_years"]
    if p["om_mode"] == 1:
        mat_r = np.where(in_w, p["om_self_mat_in"], p["om_self_mat_out"])
        rep_r = np.where(in_w, p["om_self_rep_in"], p["om_self_rep_out"])
    else:
        mat_r = np.where(in_w, p["om_out_mat_in"], p["om_out_mat_out"])
        rep_r = np.where(in_w, p["om_out_rep_in"], p["om_out_rep_out"])
    if p["cost_method"] == 1:
        # 定额法：元/kW·年 × 装机；首个运营年即含一年通胀调整
        esc_k = np.where(is_op, (1 + p["cpi"]) ** k, 0.0)
        maint = np.where(is_op, rep_r * kw / 1e4 * esc_k, 0.0)
        material = np.where(is_op, mat_r * kw / 1e4 * esc_k, 0.0)
        if p["om_mode"] == 2:
            maint = maint + np.where(is_op, p["om_out_annual"] * kw / 1e4 * esc_k, 0.0)
    else:
        # 比例法：材料费仍按元/kW定额，维修费改按固定资产净值 × 费率
        material = np.where(is_op, mat_r * kw / 1e4 * esc, 0.0)
        if p.get("om_block_rates"):
            # 分年段费率（每 5 年一档）显式给出时优先
            blk = np.clip((np.maximum(k, 1) - 1) // 5, 0, len(om_blocks) - 1)
            rep_ratio = np.where(is_op, np.asarray(om_blocks)[blk], 0.0)
            maint = np.where(is_op, nbv * rep_ratio, 0.0)
        else:
            # 网页版口径：质保期内/外各一档费率
            if p["om_mode"] == 1:
                rate_ph = np.where(in_w, p["self_rep_rate_in"], p["self_rep_rate_out"])
            else:
                rate_ph = np.where(in_w, p["out_rep_rate_in"], p["out_rep_rate_out"])
            maint = np.where(is_op, nbv * rate_ph, 0.0)

    other = p["other_y1"] * esc
    # 自维/外委其他费（元/kW；比例法下不计，与网页版一致）
    if p["om_mode"] == 1:
        oth_r = np.where(in_w, p["om_self_other_in"], p["om_self_other_out"])
    else:
        oth_r = np.where(in_w, p["om_out_other_in"], p["om_out_other_out"])
    other_fee = np.where(is_op & (p["cost_method"] != 2), oth_r * kw / 1e4 * esc, 0.0)
    sea_fee = np.where(is_op & (p["plant_type"] == 2), p["sea_area_fee"], 0.0)
    # 自定比率方式：第 1–5 年、6–10 年…各档费率直接输入（网页版 5 档）
    ins_rate = np.select([k <= 5, k <= 10, k <= 15, k <= 20],
                         [p["insurance_rate"], p["ins_rate2"],
                          p["ins_rate3"], p["ins_rate4"]],
                         default=p["ins_rate5"])
    if p["insurance_method"] == 1:
        insurance = np.where(is_op, p["insurance_base"] * p["insurance_fixed_rate"], 0.0)
    else:
        insurance = np.where(is_op, p["insurance_base"] * ins_rate, 0.0)
    land = np.where(is_op, p["land_rent"] + p["land_comp_annual"] + p["land_tax"], 0.0)
    property_tax = np.where(is_op, p["property_tax_base"] * p["property_tax_rate"], 0.0)
    storage_opex = np.where(is_op, p["storage_opex"], 0.0)

    # 储能运维明细（网页版口径）：人员 + 材料/维修（元/MWh×MWh） + 其他费（元/kW×万kW）
    stor_mwh_eq = p["cap_ac_mw"] * p["storage_ratio"] * p["storage_duration"]
    if p["om_mode"] == 1:
        raw_staff = p["storage_staff_per_100mwh"] * stor_mwh_eq / 100.0
    else:
        raw_staff = p["storage_outsource_per_100mw"] * (
            p["cap_ac_mw"] * p["storage_ratio"] * p["storage_efficiency"] / 100.0)
    stor_payroll = np.where(is_op, np.ceil(raw_staff) * p["avg_salary"]
                            * (1 + p["benefits_ratio"]), 0.0)
    if p["om_mode"] == 1:
        s_mat = np.where(in_w, p["storage_self_mat_in"], p["storage_self_mat_out"])
        s_rep = np.where(in_w, p["storage_self_rep_in"], p["storage_self_rep_out"])
        s_oth = np.where(in_w, p["storage_self_other_in"], p["storage_self_other_out"])
    else:
        s_mat = np.where(in_w, p["storage_out_mat_in"], p["storage_out_mat_out"])
        s_rep = np.where(in_w, p["storage_out_rep_in"], p["storage_out_rep_out"])
        s_oth = np.where(in_w, p["storage_out_other_in"], p["storage_out_other_out"])
    stor_detail = np.where(is_op, (s_mat + s_rep) * stor_mwh_eq / 1e4, 0.0)
    stor_other = np.where(is_op & (p["cost_method"] != 2),
                          s_oth * p["storage_ratio"] * p["cap_ac_mw"] / 10.0, 0.0)

    # 到期拆除费：按固定资产原值比例计入最后运营年
    decomm = np.where(is_op & (k == a),
                      p["decomm_ratio"] * p["fixed_asset_capex"], 0.0)

    if p["cost_method"] == 3:
        # 仅储能：电站侧运维（人工、维修、材料、其他、保险、土地、房产税、
        # 海域使用金、拆除费）全部不计，仅保留储能运维费用。
        payroll = np.zeros(n)
        maint = np.zeros(n)
        material = np.zeros(n)
        other = np.zeros(n)
        other_fee = np.zeros(n)
        insurance = np.zeros(n)
        land = np.zeros(n)
        property_tax = np.zeros(n)
        sea_fee = np.zeros(n)
        decomm = np.zeros(n)

    if int(p.get("om_cost_mode", 0)) == 1:
        _flat = float(p["total_investment"]) * float(p["om_cost_pct"])
        opex = np.where(is_op, _flat, 0.0)
        payroll = stor_payroll = maint = material = other = other_fee = np.zeros(n)
        insurance = land = property_tax = storage_opex = stor_detail = stor_other = np.zeros(n)
        sea_fee = decomm = np.zeros(n)
    else:
        opex = (payroll + stor_payroll + maint + material + other + other_fee
            + insurance + land + property_tax + storage_opex + stor_detail
            + stor_other + sea_fee + decomm)

    # ── 增值税：运营期进项税 + 建设期留抵结转 + 应交增值税 + 附加税 ──
    # 注：vat_refund 为保留位，本段及全引擎均不引用（见 DEFAULTS 注释）。
    input_vat_op = ((opex * p["vat_rate"] / (1.0 + p["vat_rate"]) * _vf)
                    if int(p.get("tariff_incl_tax", 0)) else np.zeros(n))
    vat_payable = np.zeros(n)
    vat_credit_open = np.zeros(n)
    vat_credit_used = np.zeros(n)
    vat_credit_close = np.zeros(n)
    _credit = float(p["input_vat_capex"])          # 期初留抵 = 建设期进项税
    for i in range(n):
        vat_credit_open[i] = _credit
        if not is_op[i]:
            vat_credit_close[i] = _credit
            continue
        net = output_vat[i] - input_vat_op[i]
        if net <= 0:
            _credit += -net
            vat_credit_close[i] = _credit
            continue
        use = min(_credit, net)
        _credit -= use
        vat_credit_used[i] = use
        vat_credit_close[i] = _credit
        vat_payable[i] = net - use
    surtax = vat_payable * (p["city_constr_tax"] + p["edu_surcharge"])
    # ── 增值税会计口径（T-202610-006）─────────────────────────────
    # 可抵扣进项税不构成费用：损益用不含税经营成本；现金流量表的增值税
    # 净额取「销项 − 应交 − 运营进项」，与留抵资产变动对应，避免同一笔
    # 进项税既进成本又被加回。免税/减半年度 input_vat_op 已按 _vf 折减，
    # 未抵扣部分仍留在成本中（与「免税不得抵扣」一致）。
    opex_ex_vat = opex - input_vat_op
    vat_cash_net = output_vat - vat_payable - input_vat_op
    out.update(vat_net=output_vat - vat_payable, vat_cash_net=vat_cash_net,
               opex_ex_vat=opex_ex_vat, input_vat_op=input_vat_op, vat_payable=vat_payable,
               vat_credit_open=vat_credit_open, vat_credit_used=vat_credit_used,
               vat_credit_close=vat_credit_close, surtax=surtax)

    out.update(payroll=payroll, stor_payroll=stor_payroll, maint=maint,
               material=material, other=other, other_fee=other_fee,
               insurance=insurance, land=land, property_tax=property_tax,
               storage_opex=storage_opex, stor_detail=stor_detail,
               stor_other=stor_other, sea_fee=sea_fee, decomm=decomm,
               ins_rate=ins_rate, opex=opex)

    # ── 债务：长期借款 + 流动资金借款 ──────────────────────────────────
    debt = p["debt_base_amt"] * p["debt_ratio"]
    wc_loan = p["working_capital"] * p["wc_loan_ratio"]
    equity = p["total_investment"] - debt - wc_loan

    draw = np.zeros(n)
    for i in range(t):                                  # 建设期内均匀提款
        draw[i] = debt / t
    principal = np.zeros(n)
    opening = np.zeros(n)
    bal = debt
    if p["repay_method"] == 2:                          # 等额本金
        for j in range(p["debt_tenor"]):
            if t + j < n:
                principal[t + j] = debt / p["debt_tenor"]
    else:                                               # 等额本息
        pmt = annuity_principal(debt, p["debt_rate"], p["debt_tenor"])
        for j in range(p["debt_tenor"]):
            if t + j >= n:
                break
            interest_j = bal * p["debt_rate"]
            principal[t + j] = pmt - interest_j
            bal -= principal[t + j]
    opening[0] = draw[0]
    for i in range(1, n):
        opening[i] = opening[i - 1] - principal[i - 1] + draw[i]
    # 还本窗口结束后余额应恰为 0；等额本息的年金摊还会留下 1e-12 量级残值，
    # 若不清零会令利息/ICR 在免责年份炸成天文数字。
    _end = min(t + int(p["debt_tenor"]), n)
    opening[_end:] = 0.0
    principal[_end:] = 0.0
    interest = opening * p["debt_rate"]
    # 建设期利息资本化计入 IDC、并由固定资产原值折旧回收，不再进入当期损益
    interest[:t] = 0.0
    closing = opening - principal
    debt_service = principal + interest

    # 流动资金借款：首个运营年借入、末年偿还
    wc_open = np.zeros(n)
    wc_int = np.zeros(n)
    wc_repay = np.zeros(n)
    wc_draw = np.zeros(n)
    if wc_loan > 0:
        wc_draw[t - 1] = wc_loan
        for i in range(t - 1, last):                    # 建设期末借入、末年偿还，故末年余额为 0
            wc_open[i] = wc_loan
        # 利息按「期初余额」计提：借入当年不计息，此后按上一年末余额计息
        wc_begin = np.roll(wc_open, 1)
        wc_begin[0] = 0.0
        wc_int = wc_begin * p["wc_loan_rate"]
        wc_repay[last] = wc_loan
    else:
        wc_begin = np.zeros(n)

    # ── 偿债准备金 DSRA（6 个月还本付息，由项目现金流注资）─────────────
    dsra_target = np.zeros(n)
    for i in range(n):
        j = i + 1
        dsra_target[i] = (p["dsra_months"] / 12.0) * debt_service[j] if (i >= t and j < n) else 0.0
    dsra_bal = np.zeros(n)
    dsra_fund = np.zeros(n)
    dsra_rel = np.zeros(n)
    prev = 0.0
    for i in range(n):
        if dsra_target[i] > prev:
            dsra_fund[i] = dsra_target[i] - prev
        else:
            dsra_rel[i] = prev - dsra_target[i]
        dsra_bal[i] = prev + dsra_fund[i] - dsra_rel[i]
        prev = dsra_bal[i]

    out.update(debt=debt, wc_loan=wc_loan, equity=equity, draw=draw,
               principal=principal, opening=opening, interest=interest,
               closing=closing, debt_service=debt_service,
               wc_open=wc_open, wc_begin=wc_begin, wc_int=wc_int,
               wc_repay=wc_repay, wc_draw=wc_draw,
               dsra_target=dsra_target, dsra_bal=dsra_bal,
               dsra_fund=dsra_fund, dsra_rel=dsra_rel)

    # ── 损益与税务 ─────────────────────────────────────────────────────
    # 损益按不含税经营成本（进项税不构成费用，T-202610-006）
    ebitda_p = revenue - opex_ex_vat - sales_tax - local_levy - surtax
    ebit = ebitda_p - dep - amort
    ebt = ebit - interest - wc_int

    # 所得税：亏损结转弥补（税前弥补以前年度亏损）
    taxable = np.zeros(n)
    tax = np.zeros(n)
    loss_open = np.zeros(n)
    loss_used = np.zeros(n)
    loss_close = np.zeros(n)
    loss_pool = 0.0
    for i in range(n):
        loss_open[i] = loss_pool
        if not is_op[i]:
            loss_close[i] = loss_pool
            continue
        kk = k[i]
        if p["tax_holiday_mode"] == 1:                  # 三免三减半
            if kk <= 3:
                rate = 0.0
            elif kk <= 6:
                rate = p["tax_rate"] * 0.5
            else:
                rate = p["tax_rate"]
        else:                                           # 直接免税 N 年
            rate = 0.0 if kk <= p["tax_preference_years"] else p["tax_rate"]
        base = ebt[i]
        if base < 0:
            loss_pool += -base
            loss_close[i] = loss_pool
            continue
        use = min(loss_pool, base)
        loss_pool -= use
        base -= use
        loss_used[i] = use
        loss_close[i] = loss_pool
        taxable[i] = base
        tax[i] = base * rate
    ni = ebt - tax

    # 利润分配瀑布：法定盈余公积 → 预扣税 → 未分配利润
    reserve = np.where(ni > 0, ni * p["reserve_rate"], 0.0)
    withhold_base = np.maximum(ni - reserve, 0.0)
    withholding = withhold_base * p["withholding_rate"]
    distributable = ni - reserve - withholding
    re_ = np.zeros(n)
    for i in range(1, n):
        re_[i] = re_[i - 1] + distributable[i]

    out.update(ebitda=ebitda_p, ebit=ebit, ebt=ebt, taxable=taxable, tax=tax,
               ni=ni, reserve=reserve, withholding=withholding,
               distributable=distributable, re=re_, loss_pool=loss_pool,
               loss_open=loss_open, loss_used=loss_used, loss_close=loss_close)

    # ── 现金流 ─────────────────────────────────────────────────────────
    tax_unlev = np.zeros(n)
    for i in range(n):
        if not is_op[i]:
            continue
        kk = k[i]
        if p["tax_holiday_mode"] == 1:
            rate = 0.0 if kk <= 3 else (p["tax_rate"] * 0.5 if kk <= 6 else p["tax_rate"])
        else:
            rate = 0.0 if kk <= p["tax_preference_years"] else p["tax_rate"]
        tax_unlev[i] = np.maximum(ebit[i], 0.0) * rate
    ni_unlev = ebit - tax_unlev
    wht_unlev = np.maximum(ni_unlev, 0.0) * p["withholding_rate"]
    cfads = ebitda_p - tax - withholding

    # 全投资现金流（建设期投入，运营期回收）
    # 电芯更换：按实际发生年份计入投资性现金流出（不再折现后资本化）
    repl_cf = np.zeros(n)
    _interval = (p["storage_usable_hours"] / p["storage_hours"]) if p["storage_hours"] else 0.0
    if p["storage_duration"] and _interval > 0:
        for _j in range(1, int(np.trunc(p["stor_replace_count"])) + 1):
            _idx = t + int(round(_j * _interval)) - 1
            if t <= _idx < t + a:
                repl_cf[_idx] -= p["stor_replace_unit"]

    # 全寿命周期口径的更换现值，按实际年度现金流重算，保证与现金流一致
    _d = float(p["discount_rate"])
    p["stor_replace_pv"] = -sum(float(c) / (1.0 + _d) ** i for i, c in enumerate(repl_cf))
    p["storage_invest"] = p["storage_initial_invest"] + p["stor_replace_pv"]

    cf_project = np.zeros(n)
    for i in range(t):
        # 2026-10-26 业主定：建设期利息计入全投资现金流的投资流出（资本化口径）
        cf_project[i] = -(p["cf_initial_capex"] + p["idc"]) / t
    # 增值税净流入 = 销项 − 应交 − 运营进项（净额口径，T-202610-006）
    _vat_net = vat_cash_net
    cf_project[t:] = (ebit[t:] - tax_unlev[t:] + dep[t:] + amort[t:]
                      + _vat_net[t:] + repl_cf[t:])
    cf_project[t - 1] -= p["working_capital"]  # 流动资金于建设期末投入（源模型口径）
    cf_project[last] += p["working_capital"] + salvage_value

    # 资本金现金流
    cf_equity = np.zeros(n)
    for i in range(t):
        cf_equity[i] = -(equity / t)
    cf_equity[t:] = (ni[t:] - withholding[t:] + dep[t:] + amort[t:]
                     - principal[t:] - wc_repay[t:]
                     - dsra_fund[t:] + dsra_rel[t:]
                     + _vat_net[t:] + repl_cf[t:])
    cf_equity[last] += p["working_capital"] + salvage_value

    # 建设期资本开支 / 资本金出资的逐年序列（供工作簿公式引用）
    capex_cf = np.zeros(n)
    equity_cf = np.zeros(n)
    for i in range(t):
        capex_cf[i] = -p["cf_initial_capex"] / t
        equity_cf[i] = -(equity / t)

    out.update(tax_unlev=tax_unlev, wht_unlev=wht_unlev, cfads=cfads,
               cf_project=cf_project, cf_equity=cf_equity, repl_cf=repl_cf,
               capex_cf=capex_cf, equity_cf=equity_cf)

    # ── 资产负债表（现金为轧差项）───────────────────────────────────────
    # 建设期按累计投入列示"在建工程"，投产时转入固定资产；借款与资本金
    # 亦按建设期均匀到位，故均按累计额列示。法定盈余公积计入所有者权益。
    wc = np.where((yr >= t) & (yr <= t + a), p["working_capital"], 0.0)
    wc[last] = 0.0                      # 流动资金于末年全额回收，年末不再挂账
    cip = np.zeros(n)
    debt_bal = closing.copy()
    equity_bal = np.zeros(n)
    for i in range(t):
        # 在建工程按「不含税」口径列示；进项增值税另列「可抵扣增值税形成资产」，避免重复计
        cip[i] = (p["fixed_asset_ex_vat"] + p["idc"]
                  + p["other_asset_base"]) * (i + 1) / t
        debt_bal[i] = debt * (i + 1) / t
        equity_bal[i] = equity * (i + 1) / t
    equity_bal[t:] = equity

    nbv_bs = nbv.copy()
    nbv_bs[:t] = 0.0
    nbv_bs[last] = 0.0
    amort_bs = np.zeros(n)
    run = 0.0
    for i in range(n):
        if is_op[i] and k[i] <= p["other_asset_life"]:
            run += amort[i]
        # 建设期该资产并入在建工程（cip），不重复列示（A-20）
        amort_bs[i] = (p["other_asset_base"] - run) if is_op[i] else 0.0
    amort_bs[last] = 0.0
    reserve_cum = np.cumsum(reserve)

    # 可抵扣增值税形成资产（含税模式）：建设期进项留抵未抵扣部分属资产。
    # 取【期末】留抵，与资产负债表其余科目同口径（原取期初，差一期）。
    vat_asset = np.asarray(out.get("vat_credit_close", np.zeros(n)), dtype=float).copy()
    vat_asset = np.where(np.isfinite(vat_asset), vat_asset, 0.0)
    # C-07 建设期按形象进度确认：在建工程按 (i+1)/t 累计，进项税资产同进度形成，
    # 否则 t≥2 时首年资产虚增「期初留抵×(1−1/t)」（t=2 实测 2,101.07 万元）。
    # 增值税台账（vat_credit_*）仍按税票全额列示，二者口径见 T-202610-007 报告。
    for _i in range(t):
        vat_asset[_i] = float(p["input_vat_capex"]) * (_i + 1) / t
    assets_fixed = cip + nbv_bs + amort_bs + wc + dsra_bal + vat_asset
    total_le = debt_bal + wc_open + equity_bal + reserve_cum + re_
    cash = total_le - assets_fixed          # 占位，稍后用现金流量表覆盖
    total_assets = cash + assets_fixed
    out.update(wc=wc, cip=cip, nbv_bs=nbv_bs, amort_bs=amort_bs,
               debt_bal=debt_bal, equity_bal=equity_bal, reserve_cum=reserve_cum,
               cash=cash, total_assets=total_assets, total_le=total_le,
               bs_check=total_assets - total_le,
               roe_series=ni / np.maximum(equity + reserve_cum + re_, 1e-9),
               gear_series=np.where(total_le > 0, (closing + wc_open) / np.where(
                   total_le > 0, total_le, 1.0), 0.0))

    # ── 现金流量表（交叉校验现金余额）──────────────────────────────────
    cfo = np.zeros(n)
    cfi = np.zeros(n)
    cff = np.zeros(n)
    for i in range(t):
        cfi[i] = -(p["fixed_asset_capex"] + p["other_asset_base"]) / t
        cff[i] = (debt / t) + (equity / t) - (p["idc"] / t)
    cfi[t:] = -dsra_fund[t:] + dsra_rel[t:]
    cfi[t - 1] -= p["working_capital"]      # 流动资金于建设期末投入（源模型口径）
    cfi[last] += salvage_value
    # 流动资金借款利息已计入 ni（经 ebt 扣减），不再单列；借款本金的借入与
    # 偿还属筹资活动，列入 cff。否则将与 ni 重复扣减。
    cfo[t:] = (ni[t:] + dep[t:] + amort[t:] - withholding[t:]
               + vat_cash_net[t:])       # 净利润已含 +进项，此处扣回（T-202610-006）
    cfo[last] += p["working_capital"]
    cff[t:] = -principal[t:]
    if wc_loan > 0:
        cff[t - 1] += wc_loan        # 流动资金借款于建设期末借入
        cff[last] -= wc_loan         # 于末年偿还
    cash_cf = np.cumsum(cfo + cfi + cff)
    # 现金以现金流量表为准；同时把资产负债表在现金流量表的堆叠中清空，
    # 由下方统一重算，避免"倒挤现金"天然抹平不平衡。
    cash = cash_cf.copy()
    total_assets = cash + assets_fixed
    out.update(cfo=cfo, cfi=cfi, cff=cff, cash_cf=cash_cf,
               cash_cf_check=cash - cash_cf,
               vat_asset=vat_asset, assets_fixed=assets_fixed,
               cash=cash, total_assets=total_assets,
               bs_check=total_assets - total_le)

    # ── 容错列归零 ─────────────────────────────────────────────────────
    # 网格固定 27 列（可容建设期 2 年 + 运营期 25 年）；当「建设期+运营期」
    # 小于网格长度时，尾部空档列不承载任何业务。此处统一置零，与工作簿中
    # IF(时间轴!年号>LastYear, 0, …) 的取数口径严格一致。
    active = yr <= ytot
    for _k, _v in list(out.items()):
        if _k in ("yr", "is_constr", "is_op", "k"):
            continue
        if isinstance(_v, np.ndarray) and _v.shape == (n,):
            out[_k] = np.where(active, _v, 0.0)

    # ── CAPM 反算 WACC ─────────────────────────────────────────────────
    eqr = 1.0 - p["debt_ratio"]          # 权益占比
    ki = p["tax_rate"]
    beta_l = p["beta_u"] * (1 + (1 - ki) * ((1 - eqr) / eqr if eqr > 0 else 0))
    cost_equity = p["risk_free_rate"] + beta_l * p["erp"] + p["crp"]
    wacc_capm = (1 - eqr) * p["wacc_rd"] * (1 - ki) + eqr * cost_equity
    out.update(wacc_capm=wacc_capm, beta_l=beta_l, cost_equity=cost_equity)

    # ── 指标 ───────────────────────────────────────────────────────────
    d = p["discount_rate"]
    win = slice(t, min(t + p["debt_tenor"], t + a))
    dscr = cfads[win] / debt_service[win]
    icr = ebit[win] / np.where(debt_service[win] - principal[win] > 0,
                               debt_service[win] - principal[win], np.nan)

    # LCOE（平准化度电成本，元/kWh）
    fixed_opex = (opex + sales_tax + local_levy + surtax)[t:]
    shield = (dep + amort)[t:] * ki
    pv_fixed = npv(d, fixed_opex)
    pv_shield = npv(d, shield)
    pv_salv = salvage_value / (1 + d) ** (p["oper_period"] - 1)   # 与 Excel 同口径：折现至末个运营年（首运营年指数 0）
    pv_gen = npv(d, gen[t:] / 1e4)          # 亿kWh
    lcoe = ((p["total_investment"] + pv_fixed - pv_shield - pv_salv) / pv_gen
            / 1e4) if pv_gen > 0 else float("nan")   # 万元/亿kWh → 元/kWh

    _w = float(d)
    out["metrics"] = dict(
        project_irr=irr(cf_project),
        mirr_project=mirr(cf_project, _w, _w),
        mirr_equity=mirr(cf_equity, _w, _w),
        equity_irr=irr(cf_equity),
        project_irr_pretax=irr(cf_project + tax_unlev),
        project_npv=npv(d, cf_project, t0=0),   # 2026-10-26：统一从第 0 年折现
        equity_npv=npv(d, cf_equity, t0=0),
        project_payback=payback(cf_project),
        equity_payback=payback(cf_equity),
        min_dscr=float(np.nanmin(dscr)),
        avg_dscr=float(np.nanmean(dscr)),
        min_icr=float(np.nanmin(icr)),
        avg_icr=float(np.nanmean(icr)),
        lcoe=float(lcoe),
        wacc_capm=float(wacc_capm),
        avg_roe=float(np.mean(ni[t:t + a] / np.maximum(equity + reserve_cum[t:t + a]
                                                       + re_[t:t + a], 1e-9))),
        peak_debt_ratio=float(np.nanmax(np.where(
            total_le > 0, (closing + wc_open) / np.where(total_le > 0, total_le, np.nan),
            np.nan))),
        unit_cost=float(p["total_investment"] / (p["cap_dc_mw"] * 1000) * 1e4),
        total_revenue=float(revenue.sum()),
        total_opex=float(opex.sum()),
        total_dep=float(dep.sum()),
        total_tax=float(tax.sum() + withholding.sum()),
        max_bs_error=float(np.max(np.abs(out["bs_check"]))),
        max_cash_error=float(np.max(np.abs(out["cash_cf_check"]))),
    )
    return out


def llcr(m, r=None):
    """贷款期内 CFADS 现值 / 期初贷款余额。"""
    p = m["p"]
    r = r or p["debt_rate"]
    t = m["t"]
    tenor = min(p["debt_tenor"], m["a"])
    pv = sum(m["cfads"][t + j] / (1 + r) ** (j + 1) for j in range(tenor))
    return pv / m["debt"]


# 情形开关：**只列驱动量**。派生量（建设投资、建设期利息、固定资产原值、折旧
# 基数、等效利用小时、折现率、储能投资链……）一律由驱动量按活公式重算，不得在此
# 指定——否则引擎缓存会与工作簿公式算出两个数。
#   建设投资 = 交流容量 × 单位造价 ÷ 10        → 改 capex_per_kw
#   首年等效利用小时 = 铭牌小时×(1−折减) − 储能小时×比例 → 改 nameplate_hours
#   折现率(网页版 CAPM-WACC) = (1−D/V)(Rf+βu×(1+(1−Tc)×D/E)×ERP+CRP) + D/V·Rd(1−Tc)
#                             → 改 beta_u / crp / risk_free_rate
SCENARIOS = {
    "基准": {},
    # 与 I-202610-007《100MW 融资测算》同口径（基准即此口径：不计电芯更换）
    "委托方口径（对齐 I-202610-007）": dict(replace_cost=0.0, storage_rev_on=0, withholding_rate=0.0),
    # 基准＝app 口径：储能单列计收入、预提税 5%、电芯更换 0.5 元/Wh
    # 电价下行 + 资源偏弱（≈1350 等效小时）+ 造价上行 + 风险溢价抬升（βu 抬 1/3）
    # 造价不再由 capex_per_kw 驱动 → 情形改调「电站 EPC 总价」保持同一造价水平
    #   保守 3690 元/kW ÷ 基准 3510.78 元/kW × 247,200 ≈ 259,816
    #   乐观 3340 元/kW ÷ 基准 3510.78 元/kW × 247,200 ≈ 235,150
    "保守": dict(benchmark_tariff=0.30, actual_gen_hours=1470.0, epc_price_station=3.4642,
               beta_u=0.53),
    # 电价上行 + 资源偏好（≈1500 等效小时）+ 造价下行
    "乐观": dict(benchmark_tariff=0.40, actual_gen_hours=1620.0, epc_price_station=3.1353),
    "电价含税": dict(tariff_incl_tax=1),
    # 海上风电：建设期 2 年、铭牌小时 3340（≈3200 等效小时），网格自动扩到 27 年
    "海上风电": dict(gen_type="wind", plant_type=2, construct_period=2,
                 actual_gen_hours=3340.0),
}


SRC = dict(   # 原模型基准值，用于对账
    revenue_y1=39737.25, opex_y1=3001.3637, dep=10131.7897,
    interest_y1=6718.9763, principal=12442.5487,
    project_irr=0.1159, equity_irr=0.2103,
    project_npv=131186.3351, equity_npv=155768.8927,
    dscr_avg=2.1295, dscr_min=1.8964,
)


if __name__ == "__main__":
    m = compute()
    k = m["metrics"]
    p = m["p"]
    print("=" * 72)
    print("RNE %gMW PV+储能 — %s情形（建设期 %d 年 + 运营期 %d 年）"
          % (p["cap_ac_mw"], p["scenario"], m["t"], m["a"]))
    print("=" * 72)
    i = m["t"]
    print("收益年1  营业收入 %12.2f   经营成本 %10.2f   销售税 %8.2f"
          % (m["revenue"][i], m["opex"][i], m["sales_tax"][i]))
    print("         折旧     %12.2f   利息     %10.2f   还本   %8.2f"
          % (m["dep"][i], m["interest"][i], m["principal"][i]))
    print("         总投     %12.2f   债务     %10.2f   权益   %8.2f"
          % (p["total_investment"], m["debt"], m["equity"]))
    print("-" * 72)
    print("全投资 IRR %6.2f%%    NPV %12.2f    回收期 %5.2f 年"
          % (k["project_irr"] * 100, k["project_npv"], k["project_payback"]))
    print("资本金 IRR %6.2f%%    NPV %12.2f    回收期 %5.2f 年"
          % (k["equity_irr"] * 100, k["equity_npv"], k["equity_payback"]))
    print("DSCR 最小 %6.2f    平均 %6.2f     LLCR %5.2f    ICR 最小 %6.2f"
          % (k["min_dscr"], k["avg_dscr"], llcr(m), k["min_icr"]))
    print("LCOE %6.4f 元/kWh   CAPM-WACC %6.2f%%   单位造价 %7.2f 元/W"
          % (k["lcoe"], k["wacc_capm"] * 100, k["unit_cost"]))
    print("平均 ROE %6.2f%%    峰值资产负债率 %6.2f%%"
          % (k["avg_roe"] * 100, k["peak_debt_ratio"] * 100))
    print("最大 BS 误差 %.2e   最大现金交叉误差 %.2e"
          % (k["max_bs_error"], k["max_cash_error"]))
    print("-" * 72)
    print("与源模型对账（差异为口径调整所致，详见工作簿「对账」页）：")
    for lab, got, want in [
        ("营业收入年1", m["revenue"][i], SRC["revenue_y1"]),
        ("经营成本年1", m["opex"][i], SRC["opex_y1"]),
        ("年折旧", m["dep"][i], SRC["dep"]),
        ("年利息", m["interest"][i], SRC["interest_y1"]),
        ("年还本", m["principal"][i], SRC["principal"]),
    ]:
        print("  %-12s %14.4f  vs 源 %12.4f   差 %+10.4f" % (lab, got, want, got - want))
    for lab, got, want in [
        ("全投资IRR", k["project_irr"], SRC["project_irr"]),
        ("资本金IRR", k["equity_irr"], SRC["equity_irr"]),
    ]:
        print("  %-12s %13.2f%%  vs 源 %11.2f%%   差 %+9.2fpp"
              % (lab, got * 100, want * 100, (got - want) * 100))
    print("  %-12s %14.2f  vs 源 %12.2f" % ("全投资NPV", k["project_npv"], SRC["project_npv"]))
    print("  %-12s %14.2f  vs 源 %12.2f" % ("资本金NPV", k["equity_npv"], SRC["equity_npv"]))
    print("  %-12s 最小%6.2f 平均%6.2f  vs 源 最小%6.2f 平均%6.2f"
          % ("DSCR", k["min_dscr"], k["avg_dscr"], SRC["dscr_min"], SRC["dscr_avg"]))
