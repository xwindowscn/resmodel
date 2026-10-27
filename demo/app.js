/* RES Financial Model（general） —— 界面逻辑 */
"use strict";

const S = {
  schema: null,
  values: {},
  inputs: {},
  derived: {},
  currentFile: "",
  model: null,
  view: "overview",
  table: null,
  booted: false,
  waccLive: null,
  waccTouched: false,
  waccBusy: false,
  waccFetchedAt: 0,
  waccCheckedAt: 0,
  decEdits: {},
};

const ACCENTS = [
  ["#27ae60", "#1e8449"],
  ["#2980b9", "#21618c"],
  ["#d4a017", "#b8860b"],
  ["#16a085", "#0e6655"],
  ["#e67e22", "#ba6a12"],
  ["#607d8b", "#455a64"],
  ["#c0392b", "#96281b"],
  ["#8e44ad", "#6c3483"],
  ["#2e86c1", "#1f618d"],
  ["#5c6bc0", "#3949ab"],
  ["#00897b", "#00695c"],
  ["#7b8a2f", "#5d6922"],
];

const CAT_CLASS = { 收益: "yield", 偿债: "debt", 规模: "scale", 回报: "return" };

const $ = (id) => document.getElementById(id);
const api = () => window.pywebview.api;

/* ── 启动 ─────────────────────────────────────────────── */
function applyAppName(name) {
  if (!name) return;
  document.title = name;
  const h = $("app-title");
  if (h) h.textContent = name;
}

function boot() {
  if (S.booted) return;
  S.booted = true;
  api().schema().then(async (sc) => {
    S.schema = sc;
    applyAppName(sc.appName);
    if (sc.version || sc.buildStamp) {
      const bs = $("build-stamp");
      if (bs) {
        bs.hidden = false;
        bs.textContent = `v${sc.version || ""} · ${sc.buildStamp || ""}`;
      }
    }
    buildPresets();
    buildGroups();
    buildTabs();
    // 默认项目 = 上次关闭前的数据；没有则用内置默认
    let startVals = sc.defaults;
    try {
      const last = await api().last_session();
      if (last && last.ok && last.values) {
        const known = sc.defaults || {};
        const keep = {};
        Object.entries(last.values).forEach(([k, v]) => { if (k in known || KEEP_ALWAYS.includes(k)) keep[k] = v; });
        startVals = { ...sc.defaults, ...keep };
      }
    } catch (e) { /* 读不到就用默认 */ }
    if (!startVals.ui_lang) startVals.ui_lang = "中文 (zh)";
    if (!startVals.ui_lang2) startVals.ui_lang2 = "English 英语 (en)";
    setValues(startVals);
    LicenseUI.init();
    buildProfileBar();
    await applyLang();          // 先载入词典再出数，避免首屏用中文渲染
    refreshFx();
    setInterval(refreshFx, 10 * 60 * 1000);
    watchUnits();
    await compute();
    refreshWacc(false);                       // 先读快照/兜底，立即出数
    setTimeout(() => refreshWacc(true, true), 400);   // 再后台联网刷新
    setInterval(() => refreshWacc(true, true), 10 * 60 * 1000);   // 常驻：每 10 分钟联网取数
    window.addEventListener("online", () => refreshWacc(true, true));  // 网络恢复即取
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && Date.now() - S.waccFetchedAt > STALE_MS) {
        refreshWacc(true, true);
      }
    });
  });
}

// 有网络就实时取数；超过该时长未取数即在下次窗口激活/重算时补取
const STALE_MS = 5 * 60 * 1000;
// 不在参数表中但必须随记录一起恢复的键
window.__APPJS_TAG = "v7-" + Date.now();
const KEEP_ALWAYS = ["ui_lang", "ui_lang2", "display_ccy"];

window.addEventListener("pywebviewready", boot);
window.addEventListener("DOMContentLoaded", () => {
  if (window.pywebview && window.pywebview.api) boot();
});

/* ── 左侧参数表 ───────────────────────────────────────── */
function enOf(s) {
  const m = S.schema.choicesEn || {};
  for (const k in m) {
    const i = (S.schema.choices[k] || []).indexOf(s);
    if (i >= 0 && m[k][i]) return m[k][i];
  }
  return "";
}

let I18N = {};
let I18N2 = {};

let I18N_N = null, I18N2_N = null;
const _nk = (s) => String(s || "").replace(/\s+/g, "").replace(/[＝=]/g, "=").replace(/（/g, "(").replace(/）/g, ")");
function _norm(table) {
  const out = {};
  for (const k in table) out[_nk(k)] = table[k];
  return out;
}

function T(s) {
  if (!I18N) return s;
  if (I18N[s]) return I18N[s];
  if (!I18N_N) I18N_N = _norm(I18N);
  return I18N_N[_nk(s)] || s;
}

function T2(s) {
  if (!I18N2) return "";
  if (I18N2[s]) return I18N2[s];
  if (!I18N2_N) I18N2_N = _norm(I18N2);
  return I18N2_N[_nk(s)] || "";
}

function codeOf(val, dflt) {
  const v = String(val || "").trim();
  if (!v) return dflt;
  if (v.includes("无")) return "none";
  if (/日本|日本語/.test(v)) return "ja";
  if (/Рус|俄语/.test(v)) return "ru";
  if (/English|英语/.test(v)) return "en";
  const m = v.match(/\(([A-Za-z-]{2,5})\)$/);
  return m ? m[1] : dflt;
}

function langCode() { return codeOf(S.values.ui_lang, "zh"); }
function langCode2() { return codeOf(S.values.ui_lang2, "en"); }

async function applyLang() {
  const c1 = langCode();
  const c2 = langCode2();
  try {
    const r1 = await api().i18n(c1);
    I18N = (r1 && r1.table) || {};
    I18N_N = null;
    setStatus(`lang=${c1} · ${Object.keys(I18N).length} 条`);
  } catch (e) { I18N = {}; }
  I18N2_N = null;
  try { I18N2 = (c2 === "none" || c2 === "zh") ? {} : ((await api().i18n(c2)).table || {}); }
  catch (e) { I18N2 = {}; }
  // 重建参数区与页签，让翻译生效
  const host = $("groups");
  if (host && S.schema) {
    host.innerHTML = "";
    buildGroups();
    setValues(S.values);
    applyRules();
    if (S.model) {
      renderCards(S.model.cards);
      renderDerived(S.model.derived);
      applyDisplayCurrency(S.model);
      if (S.view && S.view.startsWith("table:")) renderTable(S.table);
      if (S.view === "scenario") runScenarios();
    }
  }
  applyBiStatic(document);
  try { applyUnitLocalization(document); } catch (e) {}
  // 语言切换后重建页签，使其按新的主/副语言重新渲染
  try { const _tb = $("tabs"); if (_tb) { _tb.innerHTML = ""; buildTabs(); } } catch (e) {}

}

function pickText(cn, en, which) {
  // which: "main" | "sub"
  const c1 = langCode();
  const c2 = langCode2();
  const code = which === "main" ? c1 : c2;
  if (code === "none") return "";
  if (code === "zh" || code === "zh-CN") return cn || "";
  if (code === "zh-TW") return T(cn) || cn || "";
  if (code === "en") return en || cn || "";
  const t = which === "main" ? T(cn) : T2(cn);
  return t || en || cn || "";
}

function biHtml(cn, en) {
  if (String(cn || "").includes("\n")) return dualCell(cn);   // 「中文\nEnglish」型单元格交给 dualCell
  const main = pickText(cn, en, "main");
  const sub = pickText(cn, en, "sub");
  return esc(main) + (sub && sub !== main ? `<span class="en">${esc(sub)}</span>` : "");
}

function hintHtml(cn, en) {
  const main = pickText(cn, en, "main");
  const sub = pickText(cn, en, "sub");
  return esc(main) + (sub && sub !== main ? `<span class="en">${esc(sub)}</span>` : "");
}


/* ── 统一翻译入口（可逆；仅处理静态外壳文本） ── */
function translateStatic() {
  const c1 = langCode();
  const back = (c1 === "zh" || c1 === "zh-CN");
  if (!back && (!I18N || !Object.keys(I18N).length)) return 0;
  if (!back && !I18N_N) { I18N_N = {}; for (const k in I18N) I18N_N[_nk(k)] = I18N[k]; }
  // 占位符（placeholder 不在文本节点里）
  document.querySelectorAll("input[placeholder]").forEach((el) => {
    if (el.__phOrig === undefined) el.__phOrig = el.placeholder;
    const src = el.__phOrig;
    if (back) { el.placeholder = src; return; }
    const hm = src.match(/^[\u4e00-\u9fa5（）()：:、，,。·%\s]+?(?=[A-Za-z0-9])/);
    const key = hm ? hm[0].trim() : src.trim();
    const tr = I18N[key] || I18N_N[_nk(key)];
    if (tr && tr !== key) el.placeholder = src.replace(key, tr);
  });
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  let n = 0;
  nodes.forEach((node) => {
    const el = node.parentElement;
    if (!el || el.closest("input,textarea,script,style")) return;
    if (el.tagName === "OPTION") {
      if (node.__orig === undefined) node.__orig = node.nodeValue;
      const src0 = node.__orig;
      if (back) { if (node.nodeValue !== src0) node.nodeValue = src0; return; }
      const parts = src0.split(" / ");
      if (parts.length >= 2) {
        const k0 = parts[0].trim();
        const m0 = I18N[k0] || I18N_N[_nk(k0)];
        const s0 = (typeof T2 === "function") ? T2(k0) : "";
        if (m0) { node.nodeValue = m0 + " / " + (s0 || parts[1].trim()); n++; return; }
      }
    }
    if (el.closest(".metric-card, #table-wrap, .table-wrap")) return;   // 已由 biHtml / Python 处理
    if (node.__orig === undefined) node.__orig = node.nodeValue;
    const src = node.__orig;
    if (back) { if (node.nodeValue !== src) { node.nodeValue = src; n++; } return; }
    let txt = src.trim();
    if (!txt) return;
    let head = txt, tail = "";
    const iN = txt.indexOf("\n");
    if (iN > 0) { head = txt.slice(0, iN).trim(); tail = txt.slice(iN); }
    else {
      const m = txt.match(/^[\u4e00-\u9fa5（）()：:、，,。·%\s]+?(?=[A-Za-z0-9])/);
      if (m && m[0].trim()) { head = m[0].trim(); tail = txt.slice(m[0].length); }
    }
    const tr = I18N[head] || I18N_N[_nk(head)];
    if (!tr || tr === head) return;
    let v = src.replace(head, tr);
    // 副行：把英文尾巴换成第二语言译文
    try {
      const t2 = (typeof T2 === "function") ? T2(head) : "";
      const tailTxt = (tail || "").trim();
      if (t2 && tailTxt && tailTxt !== t2) v = v.replace(tailTxt, t2);
    } catch (e) {}
    if (node.nodeValue !== v) { node.nodeValue = v; n++; }
  });
  return n;
}
let _stTimer = null;
new MutationObserver(() => { clearTimeout(_stTimer); _stTimer = setTimeout(translateStatic, 80); })
  .observe(document.documentElement, { childList: true, subtree: true });

function buildPresets() {
  const box = $("presets");
  S.schema.scenarios.forEach((name, i) => {
    const b = document.createElement("button");
    b.innerHTML = biHtml(name, T2(name) || (S.schema.scenariosEn || [])[i] || "");
    b.dataset.scenario = name;
    if (i === 0) b.classList.add("active");
    b.addEventListener("click", () => loadPreset(name));
    box.appendChild(b);
  });
}

function syncPresetButtons(name) {
  document.querySelectorAll("#presets button").forEach((b) => {
    b.classList.toggle("active", b.dataset.scenario === name);
  });
}

/* 选择项：优先用后端提供的 fieldOptions（国别/行业/币种/Rd 方式） */
function fieldOptionsFor(key) {
  const fo = (S.schema.fieldOptions || {})[key];
  if (fo && fo.length) return fo;
  const options = (S.schema.choices || {})[key] || [];
  const optionsEn = (S.schema.choicesEn || {})[key] || [];
  return options.map((o, i) => ({ v: o, t: o, t_en: optionsEn[i] || "" }));
}

function fillSelect(el, list) {
  const cur = el.value || S.values[el.dataset.key] || "";
  el.innerHTML = "";
  list.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.v;
    let _m, _s2;
    const mm = String(o.t || "").match(/^([\u4e00-\u9fff·]+)\s+([A-Z]{2,5})$/);
    if (!o.name && mm) {              // 静态币种列表：中文名 + 代码
      const nm2 = mm[1], code2 = mm[2];
      const m1 = pickText(nm2, code2, "main");
      const s3 = pickText(nm2, code2, "sub");
      _m = `${m1} ${code2}`;
      _s2 = s3 && s3 !== m1 ? s3 : "";
      opt.textContent = _m + (_s2 ? " / " + _s2 : "");
      el.appendChild(opt);
      return;
    }
    if (o.name && o.code) {          // 币种下拉：名称随主/副语言，代码与利率保持
      const nm = pickText(o.name, o.name_en || "", "main");
      const ns = pickText(o.name, o.name_en || "", "sub");
      const tail = ` ${o.code}（10Y ${Number(o.rate).toFixed(3)}%）`;
      _m = nm + tail;
      _s2 = ns && ns !== nm ? ns : "";
    } else {
      _m = pickText(o.t || "", o.t_en || "", "main");
      _s2 = pickText(o.t || "", o.t_en || "", "sub");
    }
    opt.textContent = _m + (_s2 && _s2 !== _m ? " / " + _s2 : "");
    el.appendChild(opt);
  });
  if (list.some((o) => o.v === cur)) el.value = cur;
  else if (list.length) el.value = list[0].v;
}

function applyFieldOptions(options) {
  Object.entries(options || {}).forEach(([key, list]) => {
    const el = S.inputs[key];
    if (!el || el.tagName !== "SELECT" || !list || !list.length) return;
    el.dataset.key = key;
    fillSelect(el, list);
    S.values[key] = el.value;
  });
  applyRules();
}

async function refreshFieldOptions(country) {
  try {
    const res = await api().field_options(country || S.values.wacc_country || "");
    if (res && res.ok) {
      applyFieldOptions(res.options);
      scheduleCompute();
    } else {
      scheduleCompute();
    }
  } catch (e) {
    scheduleCompute();
  }
}


/* 单位串本地化：跟随主/副语言 + 计价货币
   · 货币型单位（万元…、元/…）拆成「货币 + 后缀」，货币取币种代码，后缀按语言翻译
   · 其他单位（年、月、天、公顷…）整体按词典翻译 */
const CUR_CN = { CNY: "人民币", USD: "美元", JPY: "日元", RUB: "卢布", EUR: "欧元", KZT: "坚戈",
  KGS: "索姆", UZS: "苏姆", TJS: "索莫尼", THB: "泰铢", IDR: "印尼盾", VND: "越南盾",
  KHR: "瑞尔", MMK: "缅元", LAK: "基普", AED: "迪拉姆", TWD: "新台币" };
function curLabel(code, which) {
  if (code === "CNY") return "元";          // 人民币沿用「万元 / 元/kWh」
  const lc = which === "main" ? langCode() : langCode2();
  if (lc === "zh" || lc === "zh-TW") return CUR_CN[code] || code;   // 中文用币种中文名
  return code;                                                     // 其他语言用币种代码（国际通用）
}

function _unitSuffix(sfx, which) {
  if (!sfx) return "";
  const tr = (x) => (which === "main" ? (T(x) || "") : (T2(x) || ""));
  const whole = tr(sfx);
  if (whole) return whole;
  const lead = /^[\/·]/.test(sfx) ? sfx[0] : "";
  const alt = lead ? sfx.slice(1) : sfx;
  const altTr = tr(alt);
  if (altTr) return lead + altTr;
  // 「/年」「/MWh·年」这类：按分隔符逐段翻译，未命中的段保留原样
  return sfx.split(/([\/·])/).map((seg) => {
    if (!seg || seg === "/" || seg === "·") return seg;
    if (!/[\u4e00-\u9fff]/.test(seg)) return seg;
    return tr(seg) || seg;
  }).join("");
}
/* 把已本地化过的单位串还原成中文源（万元、元/kWh），避免二次本地化失真 */
function normalizeUnitSrc(u) {
  let t = String(u || "");
  const code = ccyCode();
  const nm = CUR_CN[code] || "";
  if (nm) t = t.replace(new RegExp("万" + nm, "g"), "万元").replace(new RegExp(nm, "g"), "元");
  t = t.replace(new RegExp("万" + code, "g"), "万元").replace(new RegExp(code + "/", "g"), "元/");
  return t;
}

function _sfx(sfx, which) {
  if (!sfx) return "";
  const pick = (x) => (which === "main" ? T(x) : T2(x)) || "";
  return pick(sfx) || pick(sfx.replace(/^[\/·]+/, "")) && (sfx.match(/^[\/·]+/) ? sfx.match(/^[\/·]+/)[0] : "") + pick(sfx.replace(/^[\/·]+/, "")) || sfx;
}
function unitPair(cn, en) {
  const map = (S.model && S.model.unitMap) || {};
  if (cn && map[cn]) return { main: map[cn].main || cn, sub: map[cn].sub || "" };
  const code = ccyCode();
  const src = String(cn || "");
  const enSrc = String(en || "");
  let main = "", sub = "";
  if (/^万元/.test(src)) {
    const sfx = src.slice(2);
    main = `万${curLabel(code, "main")}` + _sfx(sfx, "main");
    sub = `万${curLabel(code, "sub")}` + _sfx(sfx, "sub");
  } else if (/^元\//.test(src)) {
    const sfx = src.slice(2);
    main = `${curLabel(code, "main")}/${_sfx(sfx, "main")}`;
    sub = `${curLabel(code, "sub")}/${_sfx(sfx, "sub")}`;
  } else {
    main = _sfx(src, "main");
    sub = _sfx(src, "sub") || enSrc;
  }
  if (sub === main) sub = "";
  return { main, sub };
}
function unitHtml(cn, en) {
  const pr = unitPair(cn, en);
  return esc(pr.main) + (pr.sub ? `<span class="en">${esc(pr.sub)}</span>` : "");
}

/* 后置本地化：所有单位元素按 data-src 与 unitMap 重绘（语言对 + 计价货币） */
function applyUnitLocalization(root) {
  const host = root || document;
  host.querySelectorAll(".unit").forEach((el) => {
    try {
      if (!el.dataset.src) return;
      const loc = unitPair(normalizeUnitSrc(el.dataset.src), el.dataset.srcen || "");
      const html = esc(loc.main) + (loc.sub ? `<span class="en">${esc(loc.sub)}</span>` : "");
      if (el.innerHTML !== html) el.innerHTML = html;
    } catch (e) { /* 单个单位失败不影响其余 */ }
  });
  host.querySelectorAll(".field-sub .subitem i").forEach((i2) => {
    try {
      if (!i2.dataset.src) return;
      const loc = unitPair(normalizeUnitSrc(i2.dataset.src), i2.dataset.srcen || "");
      i2.innerHTML = esc(loc.main) + (loc.sub ? `<span class="en">${esc(loc.sub)}</span>` : "");
    } catch (e) {}
  });
}

function localizeUnit(cn, en) {          // 兼容旧调用
  const pr = unitPair(cn, en);
  return { cn: pr.main, en: pr.sub };
}

function buildGroups() {
  const host = $("groups");
  S.schema.groups.forEach((g, gi) => {
    const [accent, accentD] = ACCENTS[gi % ACCENTS.length];
    const card = document.createElement("div");
    card.className = "group";
    card.style.setProperty("--accent", accent);
    card.style.setProperty("--accent-d", accentD);
    card.style.setProperty("--tint", accent + "12");

    const head = document.createElement("div");
    head.className = "group-head";
    head.innerHTML =
      `<span class="group-accent"></span>` +
      `<span class="group-num">${gi + 1}</span>` +
      `<span class="group-title">${biHtml(g.title, g.title_en)}</span>` +
      `<span class="group-chevron"></span>`;
    head.addEventListener("click", () => card.classList.toggle("collapsed"));
    card.appendChild(head);

    const body = document.createElement("div");
    body.className = "group-body";

    const dfAll = (S.schema.derivedFields || {})[g.title] || [];
    const underMap = {};
    dfAll.forEach((d) => {
      if (d.under) (underMap[d.under] = underMap[d.under] || []).push(d);
    });

    g.fields.forEach((f) => {
      const row = document.createElement("div");
      row.className = "field";
      row.dataset.key = f.key;
      row.dataset.label = (f.label + " " + f.label_en + " " + f.key).toLowerCase();

      const lab = document.createElement("label");
      lab.innerHTML = biHtml(f.label, f.label_en);
      lab.title = f.label + (f.label_en ? " / " + f.label_en : "");

      let el;
      if (f.kind === "choice") {
        el = document.createElement("select");
        el.dataset.key = f.key;
        fillSelect(el, fieldOptionsFor(f.key));
        // 下拉框宽度有限，长文本会截断 —— 用 title 让悬停可看全文
        el.title = (el.selectedOptions[0] && el.selectedOptions[0].textContent) || "";
        el.addEventListener("change", () => {
          el.title = (el.selectedOptions[0] && el.selectedOptions[0].textContent) || "";
          S.values[f.key] = el.value;
          if (f.key === "display_ccy") {
            const host = $("groups"); if (host) { host.innerHTML = ""; S.inputs = {}; buildGroups(); }
            updateFxHint(); applyLang();
          }
          if (f.key === "ui_lang" || f.key === "ui_lang2") { applyLang(); }
          if (f.key === "scenario") loadPreset(el.value);
          else if (f.key === "wacc_country") refreshFieldOptions(el.value);
          else {
            applyRules();
            scheduleCompute();
          }
        });
      } else {
        el = document.createElement("input");
        el.type = "text";
        el.spellcheck = false;
        el.autocomplete = "off";
        el.inputMode = f.kind === "text" ? "text" : "decimal";
        el.addEventListener("input", () => {
          el.title = el.value;
          const num = Number(el.value);
          S.values[f.key] = (isMoneyInput(f.key) && ccyCode() !== "CNY" && !isNaN(num))
            ? String(num * ccyScale()) : el.value;
          scheduleCompute();
        });
      }
      if (f.key === "storage_elec_price") {
        el.dataset.follow = "1";
        el.placeholder = "跟随保障收购电价";
        el.addEventListener("input", () => {
          el.dataset.follow = el.value.trim() === "" ? "1" : "0";
        });
      }
      if (isMoneyInput(f.key)) {
        const r = ccyScale();
        const raw = Number(String(S.values[f.key] ?? "").replace(/,/g, ""));
        if (!isNaN(raw) && r && r !== 1) {
          const shown = raw / r;
          el.value = String(Number(shown.toFixed(6)));
          el.dataset.disp = "1";
        }
      }
      S.inputs[f.key] = el;

      const unit = document.createElement("span");
      unit.className = "unit";
      unit.dataset.src = f.unit || "";              // 原始单位，供后置本地化反复使用
      unit.dataset.srcen = f.unit_en || "";
      const uLoc = unitPair(f.unit || "", f.unit_en || "");
      unit.innerHTML = esc(uLoc.main) + (uLoc.sub ? `<span class="en">${esc(uLoc.sub)}</span>` : "");
      unit.title = [f.unit || "", f.unit_en || ""].filter(Boolean).join(" / ");

      row.append(lab, el, unit);
      // 静态小字提示（如「实际发电小时」的填写口径）
      if (f.hint || f.hint_en) {
        const hint = document.createElement("div");
        hint.className = "field-hint";
        hint.innerHTML = hintHtml(f.hint, f.hint_en);
        row.appendChild(hint);
      }
      if (S.schema.notes && S.schema.notes[f.key]) {
        const note = document.createElement("div");
        note.className = "field-note hidden";
        note.dataset.noteKey = f.key;
        row.appendChild(note);
      }
      body.appendChild(row);

      // 紧跟该输入项的实时派生值（如 EPC 单价 → EPC 总价 / 总投资）
      const subs = underMap[f.key];
      if (subs && subs.length) {
        const sub = document.createElement("div");
        sub.className = "field-sub";
        subs.forEach((d) => {
          const sp = document.createElement("span");
          sp.className = "subitem";
          const b = document.createElement("b");
          b.textContent = "计算中…";
          sp.innerHTML = esc(d.label) + " ";
          sp.appendChild(b);
          if (d.unit) {
            const u = document.createElement("i");
            u.textContent = " " + d.unit;
            if (d.unit_en && d.unit_en !== d.unit) {
              const ue = document.createElement("span");
              ue.className = "unit-en";
              ue.textContent = d.unit_en;
              u.appendChild(ue);
            }
            sp.appendChild(u);
          }
          if (d.hint || d.hint_en) {
            const h = document.createElement("div");
            h.className = "field-hint";
            h.innerHTML = hintHtml(d.hint, d.hint_en);
            sp.appendChild(h);
          }
          sub.appendChild(sp);
          S.derived[d.key] = b;
        });
        body.appendChild(sub);
      }
    });

    // 其余只读字段（无归属输入项的）单独成行
    const df = dfAll.filter((d) => !d.under);
    df.forEach((f) => {
      const row = document.createElement("div");
      row.className = "field computed";
      row.dataset.key = f.key;
      row.dataset.label = (f.label + " " + f.label_en + " " + f.key).toLowerCase();

      const lab = document.createElement("label");
      lab.innerHTML = biHtml(f.label, f.label_en);
      lab.title = f.label + (f.label_en ? " / " + f.label_en : "");

      const val = document.createElement("span");
      val.className = "disp-value";
      val.textContent = "计算中…";
      S.derived[f.key] = val;

      const unit = document.createElement("span");
      unit.className = "unit";
      unit.dataset.src = f.unit || "";
      unit.dataset.srcen = f.unit_en || "";
      const _dp = unitPair(f.unit || "", f.unit_en || "");
      unit.innerHTML = esc(_dp.main) + (_dp.sub ? `<span class="en">${esc(_dp.sub)}</span>` : "");
      unit.title = [f.unit || "", f.unit_en || ""].filter(Boolean).join(" / ");

      row.append(lab, val, unit);
      if (f.hint || f.hint_en) {
        const h = document.createElement("div");
        h.className = "field-hint";
        h.innerHTML = hintHtml(f.hint, f.hint_en);
        row.appendChild(h);
      }
      body.appendChild(row);
    });

    card.appendChild(body);
    host.appendChild(card);
  });

  $("param-search").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    document.querySelectorAll(".group").forEach((g) => {
      let any = false;
      g.querySelectorAll(".field").forEach((f) => {
        if (f.classList.contains("rule-hide")) return;
        const hit = !q || f.dataset.label.includes(q);
        f.classList.toggle("dim", !hit);
        if (hit) any = true;
      });
      g.classList.toggle("hidden", !any);
      if (q && any) g.classList.remove("collapsed");
    });
  });
}

/* ── 选项驱动的字段显隐与方法说明 ─────────────────────── */
function ruleVisible(key) {
  const rules = S.schema.rules || [];
  for (const r of rules) {
    if (r.key !== key) continue;
    const dv = S.values[r.driver];
    if (dv == null || !r.values.includes(String(dv))) return false;
  }
  return true;
}

function applyRules() {
  document.querySelectorAll(".field[data-key]").forEach((row) => {
    row.classList.toggle("rule-hide", !ruleVisible(row.dataset.key));
  });

  // 灰化且不可填的字段（如「发电侧」下的租赁价格 → 强制 0）
  (S.schema.disableRules || []).forEach((r) => {
    const driverVal = S.values[r.driver];
    const off = r.values.indexOf(driverVal) >= 0;
    const el = S.inputs[r.key];
    const row = el && el.closest(".field");
    if (!el) return;
    el.disabled = off;
    if (row) row.classList.toggle("rule-disabled", off);
    if (off) {
      el.value = "0";
      S.values[r.key] = "0";
    }
  });

  document.querySelectorAll(".group").forEach((g) => {
    const fields = g.querySelectorAll(".field[data-key]");
    const shown = Array.from(fields).filter((f) => !f.classList.contains("rule-hide"));
    g.classList.toggle("rule-hide", fields.length > 0 && shown.length === 0);
  });

  const notes = S.schema.notes || {};
  const notesEn = S.schema.notesEn || {};
  document.querySelectorAll(".field-note").forEach((el) => {
    const key = el.dataset.noteKey;
    const txt = notes[key] && notes[key][S.values[key]];
    const txtEn = notesEn[key] && notesEn[key][S.values[key]];
    el.innerHTML = txt
      ? esc(txt) + (txtEn ? `<span class="en">${esc(txtEn)}</span>` : "")
      : "";
    el.classList.toggle("hidden", !txt);
  });
}

function filterValues(values) {
  const known = S.schema ? S.schema.defaults : {};
  const out = {};
  Object.entries(values || {}).forEach(([k, v]) => {
    if (k in known) out[k] = v;          // 丢弃旧版本已删除的参数
  });
  return out;
}

function setValues(values) {
  Object.keys(S.values).forEach((k) => {
    if (!(k in values)) delete S.values[k];
  });
  Object.entries(values).forEach(([k, v]) => {
    S.values[k] = String(v);
    const el = S.inputs[k];
    if (el) el.value = (isMoneyInput(k) && ccyCode() !== "CNY") ? (Number(v) / ccyScale()) : v;
  });
  // 兜底：把界面上所有字段都收进 S.values（含无默认值的下拉，如界面语言/计价货币）
  if (S.schema && S.schema.groups) {
    S.schema.groups.forEach((g) => g.fields.forEach((f) => {
      if (S.values[f.key] === undefined) {
        const el = S.inputs[f.key];
        S.values[f.key] = el && el.value !== undefined && el.value !== ""
          ? el.value : (f.kind === "choice" ? (fieldOptionsFor(f.key)[0] || "") : "");
      }
    }));
  }
  if (values.scenario) syncPresetButtons(values.scenario);
  if (S.schema) applyRules();
}

async function loadPreset(name) {
  const res = await api().preset(name);
  if (!res.ok) { toast(res.error, true); return; }
  S.decEdits = {};
  setValues(res.values);
  setStatus(T("已载入情景") + "：" + name);
  compute();
}

/* ── 测算记录：手动命名保存 + 关闭前自动续存 ─────────────── */
async function refreshProfileList(selectId) {
  const sel = $("profile-select");
  if (!sel) return;
  const keep = selectId || sel.value;
  let items = [];
  try { items = (await api().profiles()).items || []; } catch (e) {}
  sel.innerHTML = '<option value="">— 选择记录 —</option>';
  items.forEach((it) => {
    const o = document.createElement("option");
    o.value = it.id;
    o.textContent = `${it.name} · ${it.savedAt}`;
    sel.appendChild(o);
  });
  if (keep) sel.value = keep;
}

function buildProfileBar() {
  const btnSave = $("btn-profile-save");
  if (!btnSave) return;

  btnSave.onclick = async () => {
    const typed = ($("profile-name").value || "").trim();
    const picked = $("profile-select").value || "";
    const nm = typed || picked;           // 输入了新名字就用新名字，否则覆盖当前选中的记录
    if (!nm) { toast(T("先给这条记录起个名字，或在下拉里选一条"), true); $("profile-name").focus(); return; }
    const r = await api().save_profile(nm, S.values);
    if (!r.ok) { toast(r.error || T("保存失败"), true); return; }
    $("profile-name").value = "";
    await refreshProfileList(r.id);
    setStatus(T("已保存记录") + "：" + nm);
  };

  $("profile-select").onchange = async (e) => {
    const pid = e.target.value;
    if (!pid) return;
    const r = await api().load_profile(pid);
    if (!r.ok) { toast(r.error || T("载入失败"), true); return; }
    S.decEdits = {};
    const keepLang = {};
    KEEP_ALWAYS.forEach((k) => { if (r.values && r.values[k] !== undefined) keepLang[k] = r.values[k]; });
    setValues({ ...S.schema.defaults, ...filterValues(r.values), ...keepLang });
    applyLang();
    compute();
    setStatus(T("已载入记录") + "：" + r.name);
  };

  $("btn-profile-del").onclick = async () => {
    const pid = $("profile-select").value;
    if (!pid) { toast(T("先在下拉里选一条记录"), true); return; }
    if (!window.confirm(T("删除这条记录？"))) return;
    await api().delete_profile(pid);
    await refreshProfileList();
    setStatus(T("已删除记录"));
  };

  refreshProfileList();
}

// 关窗/隐藏时立即续存（不依赖防抖）
["pagehide", "beforeunload"].forEach((ev) =>
  window.addEventListener(ev, () => {
    try { api().autosave(S.values); } catch (e) {}
  })
);

let _autosaveTimer = null;
function scheduleAutosave() {
  clearTimeout(_autosaveTimer);
  _autosaveTimer = setTimeout(() => {
    try { api().autosave(S.values); } catch (e) {}
  }, 800);
}

/* ── 页签 ─────────────────────────────────────────────── */
function buildTabs() {
  const box = $("tabs");
  const tabs = [{ id: "overview", label: "概览", en: "Overview" }]
    .concat(S.schema.tables.map((t) => ({
      id: "table:" + t.name, label: t.name, en: t.name_en || "",
    })))
    .concat([{ id: "scenario", label: "情景对比", en: "Scenario Comparison" },
             { id: "sens", label: "敏感度分析", en: "Sensitivity" }]);

  tabs.forEach((t, i) => {
    const b = document.createElement("button");
    b.innerHTML = biHtml(t.label, t.en);
    b.dataset.tab = t.id;
    if (i === 0) b.classList.add("active");
    b.addEventListener("click", () => switchView(t.id));
    box.appendChild(b);
  });
}

function setTitle(cn, en) {
  $("view-title").innerHTML = biHtml(cn, en);
}

function switchView(id) {
  S.view = id;
  document.querySelectorAll("#tabs button").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === id);
  });
  $("view-overview").classList.toggle("hidden", id !== "overview");
  // 「敏感度分析」也渲染在 #table-wrap 里，不能把整个 view-table 容器藏掉
  $("view-table").classList.toggle("hidden", !(id.startsWith("table:") || id === "sens"));
  $("view-scenario").classList.toggle("hidden", id !== "scenario");

  if (id === "overview") {
    setTitle("核心指标", "Key Metrics");
    if (S.model) renderCharts(S.model.chart);
  } else if (id.startsWith("table:")) {
    S.table = id.slice(6);
    const t = S.schema.tables.find((x) => x.name === S.table);
    setTitle(S.table, (t && t.name_en) || "");
    if (S.model) renderTable(S.table);
  } else if (id === "sens") {
    setTitle("敏感度分析", "Sensitivity Analysis");
    runSensitivity();
  } else {
    setTitle("情景对比", "Scenario Comparison");
    runScenarios();
  }
}

/* ── 计算 ─────────────────────────────────────────────── */
let timer = null;
let seq = 0;

function scheduleCompute() {
  clearTimeout(timer);
  timer = setTimeout(compute, 320);
}

async function compute() {
  clearTimeout(timer);
  const my = ++seq;
  setStatus(T("计算中…"), "busy");
  try {
    const res = await api().compute({ ...S.values });
    if (my !== seq) return;
    if (!res.ok) {
      if (res.gated) {
        LicenseUI.showGate(res.license);
        setStatus(T("需要授权"), "err");
        return;
      }
      setStatus(T("计算失败"), "err");
      toast(res.error, true);
      return;
    }
    S.model = res;
    render(res);
    setStatus(`已更新 Updated · ${res.elapsed}s`);
    // 网络可用时按需补取实时数（限频，避免逐键刷新）
    if (navigator.onLine !== false &&
        Date.now() - S.waccCheckedAt > 2 * 60 * 1000) {
      refreshWacc(true, true);
    }
  } catch (e) {
    if (my !== seq) return;
    setStatus(T("计算失败"), "err");
    toast(String(e), true);
  }
}

function applyDisplayCurrency(res) {
  const c = (res && res.ccy) || null;
  const usd = !!c && c.code !== "CNY";
  const lc = langCode();
  const useEn = lc !== "zh" && lc !== "zh-TW";          // 非中文界面用英文/代码写法
  const cn = usd ? (useEn ? (c.unit_en || c.unit) : c.unit) : (useEn ? "10K CNY" : "万元");
  const enTxt = usd ? (c.unit_en || c.unit) : "10K CNY";
  const prefix = usd ? c.prefix : "元";
  document.querySelectorAll(".unit").forEach((el) => {
    if (el.dataset && el.dataset.src) return;           // 已由 unitMap 统一管理，勿覆盖
    const t = el.firstChild;
    if (t && t.nodeType === 3) {
      const txt = t.textContent.trim();
      if (txt === "万元" || txt === "万美元") t.textContent = cn;
      else if (usd && txt.indexOf("元/") === 0) t.textContent = prefix + "/" + txt.slice(2);
    }
    const en = el.querySelector(".en");
    if (en) {
      const e = en.textContent.trim();
      if (e === "10K CNY" || /^10K [A-Z]{3}$/.test(e)) en.textContent = enTxt;
    }
  });
  const hint = $("table-hint");
  if (hint) {
    hint.innerHTML = hint.innerHTML
      .replace(/单位：(万)?[^<·\n]*?元/g, "单位：" + cn)
      .replace(/Unit: 10K [A-Z]{3}/g, "Unit: " + enTxt);
  }
}

function render(res) {
  applyDisplayCurrency(res);
  scheduleAutosave();
  renderMeta(res.summary);
  renderDerived(res.derived);
  renderCards(res.cards);
  renderCharts(res.chart);
  renderFirstYear(res.firstYear);
  if (S.waccLive) renderWaccChip(S.waccLive);
  if (S.view.startsWith("table:")) renderTable(S.table);
  if (S.view === "scenario") runScenarios();
}

function renderMeta(s) {
  $("meta-line").innerHTML =
    `<span class="chip">${biText("建设期", "Construction")} <b>${s.construct}</b> ${yearUnit()}</span>` +
    `<span class="chip">${biText("运营期", "Operation")} <b>${s.operate}</b> ${yearUnit()}</span>` +
    `<span class="chip">${biText("总投资", "Investment")} <b>${fmt(s.investment, 0)}</b> ${chipUnit()}</span>` +
    `<span class="chip">${biText("权益", "Equity")} <b>${fmt(s.equity, 0)}</b> ${chipUnit()}</span>` +
    `<span class="chip">${biText("债务", "Debt")} <b>${fmt(s.debt, 0)}</b> ${chipUnit()}</span>` +
    `<span class="chip">WACC <b>${(s.wacc * 100).toFixed(2)}%</b></span>`;
}

let FX_TABLE = { CNY: 1, USD: 7 };
let FX_SRC = "fallback";

function ccyCode() {
  const v = String(S.values.display_ccy || "CNY").trim();
  const m = v.match(/([A-Z]{3})$/);
  return m ? m[1] : (v || "CNY");
}



/* 概览小卡的单位：跟随计价货币（中文 ccy.unit / 英文 ccy.unit_en） */
function yearUnit() {
  const c = langCode();
  if (c === "zh" || c === "zh-TW") return "年";
  if (c === "en") return "yrs";
  return T("年") || "年";
}

function chipUnit() {
  const c = (S.model && S.model.ccy) || {};
  const lc = langCode();
  const useEn = lc !== "zh" && lc !== "zh-TW";   // 非中文界面用英文/代码写法
  return esc((useEn ? (c.unit_en || c.unit) : (c.unit || c.unit_en)) || "万元");
}

function ccyScale() {
  const c = ccyCode();
  return c === "CNY" ? 1 : (FX_TABLE[c] || FX_TABLE.USD || 7);
}

async function refreshFx() {
  try {
    const r = await api().fx_rate();
    if (r && r.ok && r.rates) {
      const cny = r.usd_cny || 7;
      const t = { CNY: 1 };
      Object.entries(r.rates).forEach(([k, v]) => { if (v > 0) t[k] = cny / v; });
      FX_TABLE = t;
      FX_SRC = r.source === "live" ? "联网实时" : "离线兜底";
      updateFxHint();
    }
  } catch (e) { /* 离线忽略 */ }
}

function updateFxHint() {
  const row = document.querySelector('[data-key="display_ccy"]');
  if (!row) return;
  let h = row.querySelector(".fx-hint");
  if (!h) {
    h = document.createElement("div");
    h.className = "field-hint fx-hint";
    row.appendChild(h);
  }
  const c = ccyCode();
  const rate = ccyScale();
  const usd = FX_TABLE.USD || 7;
  let txt = `汇率：1 美元 = ${usd.toFixed(4)} 元（${FX_SRC}）`;
  if (c !== "CNY" && c !== "USD") txt += `；1 ${c} = ${rate.toFixed(4)} 元`;
  h.textContent = txt;
}

function isMoneyInput(k) {
  const f = (S.schema.groups || []).flatMap((g) => g.fields).find((x) => x.key === k);
  const u = String((f && f.unit) || "");
  if (!u || u.indexOf("美元") >= 0 || u === "元/美元") return false;
  return u.startsWith("万元") || u.startsWith("元/");
}

function ccyIsUsd() {
  return String(S.values.display_ccy || "").toUpperCase().includes("USD");
}



function renderDerived(d) {
  if (!d) return;
  const storTariff = S.inputs["storage_elec_price"];
  if (storTariff && d["d_guar_tariff"]) {
    storTariff.placeholder = "跟随 " + d["d_guar_tariff"];
    if (storTariff.dataset.follow === "1") {
      const v = String(d["d_guar_tariff"]).replace(/,/g, "");
      storTariff.value = v;
      S.values["storage_elec_price"] = v;
    }
  }
  Object.keys(d).forEach((k) => {
    const el = S.derived[k];
    if (el) el.textContent = d[k];
  });
  try { applyUnitLocalization(document); } catch (e) {}
}

function renderCards(cards) {
  const host = $("cards");
  host.innerHTML = "";
  cards.forEach((c) => {
    const div = document.createElement("div");
    div.className = "metric-card cat-" + (CAT_CLASS[c.cat] || "yield");
    const unit = c.kind === "pct" ? "" : (c.unit || "");
    div.innerHTML =
      `<div class="metric-top"><span class="metric-label">` +
      `${biHtml(c.label, c.label_en)}</span>` +
      `<span class="metric-tag">${biHtml(c.cat, c.cat_en)}</span></div>` +
      `<div class="metric-value">${c.text}` +
      (unit ? `<span class="metric-unit">${esc(unit)}` +
              (c.unit_en && c.unit_en !== unit
                ? `<span class="unit-en">${esc(c.unit_en)}</span>` : "") +
              `</span>` : "") +
      `</div>`;
    const v = div.querySelector(".metric-value");
    if (c.text.length > 10) v.style.fontSize = "18px";
    else if (c.text.length > 8) v.style.fontSize = "20px";
    host.appendChild(div);
  });
}

function renderFirstYear(items) {
  const host = $("first-year");
  host.innerHTML = items
    .map((it) => `<div class="fy-item"><span class="l">` +
                 `${biHtml(it.label, it.label_en)}</span>` +
                 `<span class="v">${fmt(it.value, 1)}</span></div>`)
    .join("");
}

/* ── 表格 ─────────────────────────────────────────────── */
const esc = (s) => String(s).replace(/[&<>"]/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function tableHead(cols, colsEn) {
  return "<thead><tr>" + cols.map((c, i) =>
    `<th>${biHtml(c, (colsEn || [])[i] || "")}</th>`).join("") +
    "</tr></thead><tbody>";
}

function seriesHtml(t, idx) {
  // 转置布局：行＝指标，列＝年份（建设期在前，运营期随后）
  const years = t.rows.map((r) => r.cells || []);
  let html = "<thead><tr><th>" + biHtml("项目年", "Project Year") + "</th>" +
    years.map((c) => `<th>${c[0] ?? ""}</th>`).join("") + "</tr>";
  html += "<tr><th>" + biHtml("运营年", "Operating Year") + "</th>" +
    years.map((c) => `<th>${c[1] ?? ""}</th>`).join("") + "</tr></thead><tbody>";
  for (let ci = 2; ci < t.cols.length; ci++) {
    const head = biHtml(t.cols[ci], (t.cols_en || [])[ci] || "");
    html += `<tr><td class="txt rowhead">${head}</td>` +
      years.map((c) => {
        const kind = t.kinds[ci];
        let cell = c[ci];
        let extra = "";
        if (kind !== "int" && kind !== "op" && String(cell).startsWith("-"))
          extra = ' class="neg"';
        return `<td${extra}>${cell}</td>`;
      }).join("") + "</tr>";
  }
  return html + "</tbody>";
}

function renderSeriesTable(t) {
  return seriesHtml(t, t.cols.map((_, i) => i));
}

// 列放不下一屏时，按列切块、每块重复前两列（项目年/运营年），纵向排列
function layoutTableBlocks(t, table) {
  const wrap = table.parentElement;
  const avail = wrap.clientWidth - 20;
  if (!avail || avail < 240) return;
  const ths = table.querySelectorAll("thead th");
  if (ths.length < 4) return;
  const w = [...ths].map((th) => th.getBoundingClientRect().width);
  const keyW = w[0] + w[1];
  const groups = [];
  let cur = [], used = keyW;
  for (let i = 2; i < t.cols.length; i++) {
    const cw = w[i] + 10;
    if (cur.length && used + cw > avail) {
      groups.push(cur); cur = []; used = keyW;
    }
    cur.push(i); used += cw;
  }
  if (cur.length) groups.push(cur);
  if (groups.length < 2) return;

  wrap.innerHTML = "";
  groups.forEach((g, gi) => {
    const el = document.createElement("table");
    el.className = "data-table series-table table-block";
    if (gi === 0) el.id = "data-table";
    el.innerHTML = seriesHtml(t, [0, 1].concat(g));
    wrap.appendChild(el);
  });
}

const DEC_COLS8 = '<colgroup>' + '<col style="width:12.5%">'.repeat(8) +
  '</colgroup>';
const DEC_COLS6 = '<colgroup><col style="width:5%"><col style="width:30%">' +
  '<col style="width:14%"><col style="width:27%"><col style="width:12%">' +
  '<col style="width:12%"></colgroup>';

function renderDecisionTable(t) {
  return (t.blocks || []).map((block, bi) => {
    let html = `<table class="data-table dec-table">${bi === 0 ? DEC_COLS8 : DEC_COLS6}<tbody>`;
    block.forEach((row) => {
      const cls = row.cls ? ` class="${row.cls}"` : "";
      const meta = (row.sec
        ? ` data-sec="${row.sec}" data-key="${row.key}"` +
          ` data-unit="${row.unit || "W"}" data-param="${row.param || ""}"`
        : "") + (row.role ? ` data-row-role="${row.role}"` : "");
      html += `<tr${cls}${meta}>` + row.cells.map((cell) => {
        const span = cell.span > 1 ? ` colspan="${cell.span}"` : "";
        let sty = "";
        if (cell.align) sty += `text-align:${cell.align};`;
        if (cell.pad) sty += `padding-right:${cell.pad};`;
        const align = sty ? ` style="${sty}"` : "";
        let inner;
        if (cell.input === "num") {
          inner = `<input type="number" step="0.0001" class="dec-inp num"` +
                  ` data-role="price" value="${esc(cell.value ?? "")}">`;
        } else if (cell.input === "text") {
          const role = cell.span > 1 ? "note" : "desc";
          inner = `<input type="text" class="dec-inp txt"` +
                  ` data-role="${role}" value="${esc(cell.value ?? "")}">`;
        } else if (cell.amount) {
          inner = `<span class="dec-amt">${dualCell(cell.t)}</span>`;
        } else if (cell.bal) {
          inner = `<strong>= <span class="dec-bal" data-bal="${cell.bal}">` +
                  `${esc(cell.t)}</span></strong>`;
        } else if (cell.sub) {
          inner = `<strong><span class="dec-sub" data-sub="${cell.sub}">` +
                  `${esc(cell.t)}</span></strong>`;
        } else {
          const tag = cell.strong ? "strong" : "span";
          inner = `<${tag}>${dualCell(cell.t)}</${tag}>`;
        }
        return `<td${span}${align}>${inner}</td>`;
      }).join("") + "</tr>";
    });
    return html + "</tbody></table>";
  }).join("");
}

/* 决策表：内容/单价/备注可改；金额与三行结余随输入实时重算 */
function decisionCtx(t) {
  S.decDC = Number(t.dc_mw) || 0;
  S.decMwh = Number(t.storage_mwh) || 0;
  S.decTI = Number(t.total_inv) || 0;
}

function decisionEdit(key) {
  return S.decEdits[key] || (S.decEdits[key] = {});
}

function applyDecisionEdits() {
  document.querySelectorAll("#table-wrap tr[data-sec]").forEach((tr) => {
    const ed = S.decEdits[tr.dataset.key];
    if (!ed) return;
    tr.querySelectorAll("input.dec-inp").forEach((el) => {
      const v = ed[el.dataset.role];
      if (v != null) el.value = v;
    });
  });
}

function decRecalc() {
  const dc = S.decDC || 0;
  const mwh = S.decMwh || 0;
  const sums = { 2: 0, 3: 0, 4: 0 };
  let adjTr = null;
  document.querySelectorAll("#table-wrap tr[data-sec]").forEach((tr) => {
    if (tr.dataset.rowRole === "adj") { adjTr = tr; return; }
    const sec = Number(tr.dataset.sec);
    const inp = tr.querySelector("input.dec-inp.num");
    const price = inp ? parseFloat(inp.value) : 0;
    const mult = tr.dataset.unit === "Wh" ? mwh * 100 : dc * 100;
    const amt = (isFinite(price) ? price : 0) * mult;
    const span = tr.querySelector(".dec-amt");
    if (span) span.textContent = Math.abs(amt) < 0.05 ? "—" : fmt(amt, 1);
    if (sums[sec] != null) sums[sec] += amt;
  });
  const ti = S.decTI || 0;
  const b2 = ti - sums[2] - sums[3];
  let sec4 = sums[4];
  if (adjTr) {
    // 其他 Others：金额 = 第 3 项结余 − 第 4 项其余各项之和；单价按总直流容量反推
    const adjAmt = b2 - sec4;
    const adjInp = adjTr.querySelector("input.dec-inp.num");
    const adjSpan = adjTr.querySelector(".dec-amt");
    if (adjInp) {
      const mult = adjTr.dataset.unit === "Wh" ? mwh * 100 : dc * 100;
      adjInp.value = (mult ? adjAmt / mult : 0).toFixed(4);
      adjInp.readOnly = true;
      adjInp.title = "按第 3 项结余反推 Back-solved from balance";
      adjInp.style.background = "#eef3f7";
      adjInp.style.color = "#1f5051";
    }
    if (adjSpan) adjSpan.textContent = fmt(adjAmt, 1);
    sec4 += adjAmt;
  }
  const subs = { s1: ti, s2: sums[2], s3: sums[3], s4: sec4 };
  Object.entries(subs).forEach(([k, v]) => {
    const el = document.querySelector(`.dec-sub[data-sub="${k}"]`);
    if (el) el.textContent = fmt(v, 1);
  });
  const bal = {
    b1: ti - sums[2],
    b2: b2,
    b3: ti - sums[2] - sums[3] - sec4,
  };
  Object.entries(bal).forEach(([k, v]) => {
    const el = document.querySelector(`.dec-bal[data-bal="${k}"]`);
    if (!el) return;
    // 末行结余恒为 0 并显示出来
    if (k === "b3") { el.textContent = fmt(0, 1); return; }
    el.textContent = Math.abs(v) < 0.05 ? "—" : fmt(v, 1);
  });
  const b3tr = document.querySelector('.dec-bal[data-bal="b3"]');
  const last = b3tr && b3tr.closest("tr") && b3tr.closest("tr").lastElementChild;
  if (last && last.textContent.indexOf("EPC") >= 0 && dc) {
    last.textContent = `EPC 造价 Price ${fmt(sec4 / (dc * 100), 2)} 元/W`;
  }
}

function onDecisionEdit(e) {
  const el = e.target;
  if (!el.classList || !el.classList.contains("dec-inp")) return;
  const tr = el.closest("tr[data-sec]");
  if (!tr) return;
  const role = el.dataset.role;
  const param = tr.dataset.param;
  // 对应模型参数的单价由重算回填，不本地暂存，避免参数变动后旧值残留
  if (!(role === "price" && param)) {
    decisionEdit(tr.dataset.key)[role] = el.value;
  }
  decRecalc();
  if (e.type === "change" && role === "price" && param) {
    const v = parseFloat(el.value);
    if (!isFinite(v)) return;
    S.values[param] = String(v);
    if (S.inputs[param]) S.inputs[param].value = String(v);
    scheduleCompute();
  }
}

function wireDecisionTable(t) {
  decisionCtx(t);
  const wrap = $("table-wrap");
  watchBiGap();
  watchUnits();
  queueMicrotask(() => applyBiGap(wrap));
  if (wrap.dataset.decWired !== "1") {
    wrap.dataset.decWired = "1";
    wrap.addEventListener("input", onDecisionEdit);
    wrap.addEventListener("change", onDecisionEdit);
  }
  applyDecisionEdits();
  decRecalc();
}


/* 复合单元格：「中文\nEnglish」或「甲 + 乙」这类复合标签，按主/副语言逐段翻译 */
function _trSeg(x, which) {
  const t = which === "main" ? T(x) : T2(x);
  return (t && t !== x) ? t : "";
}
function _joinSegs(zh, which, en) {
  const segs = zh.split(/\s*([+＋\-−×÷=＝])\s*/).map((v) => v.trim()).filter(Boolean);
  let ok = 0;
  const out = segs.map((v) => {
    if (!/[\u4e00-\u9fff]/.test(v)) return v;
    const t = _trSeg(v, which);
    if (t) { ok++; return t; }
    return which === "main" ? v : "";
  }).filter((v) => v !== "").join(" + ");
  return { text: out, hit: ok, total: segs.filter((v) => /[\u4e00-\u9fff]/.test(v)).length };
}
function dualCell(v) {
  const s0 = String(v ?? "");
  if (!s0) return "";
  const parts = s0.split("\n");
  const zh = parts[0] || "";
  const en = parts.length > 1 ? parts.slice(1).join("\n") : "";
  if (!/[\u4e00-\u9fff]/.test(zh)) return esc(zh);          // 纯数值/编号
  // 先尝试整串命中（公式句、带括号的长句），再退化为按运算符逐段翻译
  const wholeM = _trSeg(zh, "main"), wholeS = _trSeg(zh, "sub");
  if (wholeM) {
    const mainW = wholeM;
    let subW = wholeS || en;
    if (subW === mainW) subW = "";
    return esc(mainW) + (subW ? `<span class="en">${esc(subW)}</span>` : "");
  }
  const m = _joinSegs(zh, "main", en);
  const s1 = _joinSegs(zh, "sub", en);
  const main = m.hit ? m.text : (en || zh);
  let sub = s1.hit ? s1.text : en;
  if (sub === main) sub = "";
  return esc(main) + (sub ? `<span class="en">${esc(sub)}</span>` : "");
}
function renderDefTable(t) {
  let html = tableHead(t.cols, t.cols_en);
  t.rows.forEach((row) => {
    const cls = row.cls ? ` class="${row.cls}"` : "";
    html += `<tr${cls}>` + row.cells.map((cell, i) => {
      const neg = i === 1 && /^-/.test(String(cell)) ? ' class="neg"' : "";
      return `<td${neg}>${dualCell(cell)}</td>`;
    }).join("") + "</tr>";
  });
  return html + "</tbody>";
}

function renderMatrixTable(t) {
  const base = typeof t.base === "number" ? t.base : t.cols.indexOf("基准");
  let html = "<thead><tr>" + t.cols.map((c, i) =>
    `<th${i === base ? ' class="base"' : ""}>` +
    `${biHtml(c, (t.cols_en || [])[i] || "")}</th>`).join("") +
    "</tr></thead><tbody>";
  t.rows.forEach((row) => {
    html += "<tr>" + row.cells.map((cell, i) => {
      const neg = i > 0 && /^-/.test(String(cell)) ? " neg" : "";
      const baseCls = i === base ? " base" : "";
      return `<td class="${(neg + baseCls).trim()}">${dualCell(cell)}</td>`;
    }).join("") + "</tr>";
  });
  return html + "</tbody>";
}


/* 同一单元格内主/副语言：同行时空两格；单元格多行时让副语言另起一行 */
function applyBiGap(root) {
  const host = root || document;
  host.querySelectorAll("td .en, th .en").forEach((el) => {
    const cell = el.closest("td, th");
    if (!cell) return;
    const cs = getComputedStyle(cell);
    const lh = parseFloat(cs.lineHeight) || (parseFloat(cs.fontSize) * 1.4) || 16;
    const multi = cell.getBoundingClientRect().height > lh * 1.45;
    el.classList.toggle("block", multi);
  });
}

let _unitObs = false;
function watchUnits() {
  if (_unitObs) return;
  _unitObs = true;
  let t = null;
  new MutationObserver(() => {
    clearTimeout(t);
    t = setTimeout(() => { try { applyUnitLocalization(document); } catch (e) {} }, 150);
  }).observe(document.body, { childList: true, subtree: true });
}

let _biGapObserved = false;
function watchBiGap() {
  if (_biGapObserved) return;
  const wrap = $("table-wrap");
  if (!wrap) return;
  _biGapObserved = true;
  new MutationObserver(() => applyBiGap(wrap)).observe(wrap, { childList: true, subtree: true });
}

function renderTable(name) {
  const t = S.model.tables[name];
  if (!t) return;
  const title = t.title || name;
  const titleEn = t.title_en || t.name_en || "";
  $("table-title").innerHTML = biHtml(title, titleEn);
  setTitle(title, titleEn);

  const hint = $("table-hint");
  const foot = $("table-foot");
  const wrap = $("table-wrap");
  wrap.innerHTML = '<table class="data-table" id="data-table"></table>';
  const table = $("data-table");
  table.className = "data-table";
  foot.classList.add("hidden");
  foot.textContent = "";

  if (t.type === "glossary") {
    hint.innerHTML = biHtml("模型术语与缩写", "Terms and abbreviations");
    renderGlossary(t);
    return;
  }

  let html;
  if (t.type === "decision") {
    hint.innerHTML = biHtml(
      "网页同款格式 · 单位：万元 · 末项「其他」按第 3 项结余反推使结余为 0",
      "Web-model layout · 10K CNY · “Others” back-solved from balance");
    wrap.innerHTML = renderDecisionTable(t);
    wireDecisionTable(t);
    if (t.footer) {
      foot.textContent = t.footer;
      foot.classList.remove("hidden");
    }
    return;
  } else if (t.type === "combo") {
    hint.innerHTML = biHtml(
      "计算过程 · 三币种对比 · 敏感度（同页依次排列）",
      "Calculation steps · currency comparison · sensitivity (top to bottom)");
    wrap.innerHTML = (t.sections || []).map((s) => {
      const cls = s.type === "matrix"
        ? "data-table matrix-table" : "data-table def-table";
      const body = s.type === "matrix" ? renderMatrixTable(s) : renderDefTable(s);
      return `<div class="combo-sec">` +
        `<div class="combo-title">${biHtml(s.title || "", s.title_en || "")}</div>` +
        `<table class="${cls}">${body}</table>` +
        (s.footer ? `<div class="combo-foot">${esc(s.footer)}</div>` : "") +
        `</div>`;
    }).join("");
    if (t.footer) {
      foot.textContent = t.footer;
      foot.classList.remove("hidden");
    }
    return;
  } else if (t.type === "matrix") {
    table.classList.add("matrix-table");
    hint.innerHTML = biHtml(
      "行＝债务成本 Rd，列＝国别风险溢价 CRP · ★ 为当前口径",
      "Rows = cost of debt Rd, cols = country risk premium CRP · ★ current case");
    html = renderMatrixTable(t);
  } else if (t.type === "def") {
    table.classList.add("def-table");
    hint.innerHTML = biHtml(
      "计算过程表 · 数值随左侧参数实时重算",
      "Calculation table · recalculated live from sidebar inputs");
    html = renderDefTable(t);
  } else {
    table.classList.add("series-table");
    hint.innerHTML = biHtml(
      "单位：万元 · 建设期行以浅蓝底标示",
      "Unit: 10K CNY · Construction-period rows shaded blue");
    html = renderSeriesTable(t);
  }

  table.innerHTML = html;
  // 不再按列切块：整表横向排布，超宽时左右滚动查看（见 app.css 的 sticky 前两列）
  if (t.footer) {
    foot.textContent = t.footer;
    foot.classList.remove("hidden");
  }
}

function renderGlossary(t) {
  const wrap = $("table-wrap");
  const cols = t.cols || [], colsEn = t.cols_en || [];
  let html = "<thead><tr>" + cols.map((c, i) =>
    `<th>${biHtml(c, colsEn[i] || "")}</th>`).join("") + "</tr></thead><tbody>";
  (t.rows || []).forEach((r) => {
    html += "<tr>" + r.map((v, i) =>
      `<td class="txt${i === 0 ? " term" : ""}">${dualCell(v)}</td>`).join("") + "</tr>";
  });
  wrap.innerHTML = `<table class="data-table gloss-table">${html}</tbody></table>`;
}

async function runTermSensitivity() {
  const box = $("term-sens");
  if (!box) return;
  try {
    const res = await api().term_sensitivity({ ...S.values });
    if (!res.ok) { box.innerHTML = `<div class="sens-loading">${esc(res.error || "计算失败")}</div>`; return; }
    let h = '<table class="data-table sens-table"><thead><tr>' +
      "<th>" + biHtml("借款期限", "Loan tenor") + "</th>" +
      "<th>" + biHtml("全投资 IRR", "Project IRR") + "</th>" +
      "<th>" + biHtml("资本金 IRR", "Equity IRR") + "</th>" +
      "<th>" + biHtml("资本金 MIRR", "Equity MIRR") + "</th>" +
      "<th>" + biHtml("最小 DSCR", "Min DSCR") + "</th></tr></thead><tbody>";
    (res.rows || []).forEach((r) => {
      const isBase = Math.abs(r.term - (S.values.debt_tenor || 10)) < 0.5;
      h += `<tr${isBase ? ' class="base-row"' : ""}><td class="txt term">${r.term} 年</td>` +
        `<td>${(r.pirr * 100).toFixed(2)}%</td>` +
        `<td>${(r.eirr * 100).toFixed(2)}%</td>` +
        `<td>${(r.emirr * 100).toFixed(2)}%</td>` +
        `<td>${r.dscr.toFixed(2)}</td></tr>`;
    });
    box.innerHTML = h + "</tbody></table>";
  } catch (e) {
    box.innerHTML = `<div class="sens-loading">${esc(String(e))}</div>`;
  }
}

async function runSensitivity() {
  const wrap = $("table-wrap");
  // 面板标题默认写死为「损益表」，进敏感度页必须覆盖，否则左上角残留旧表名
  $("table-title").innerHTML = biHtml("敏感度分析", "Sensitivity Analysis");
  wrap.innerHTML = '<div class="sens-loading">计算中… Computing 15 组情景</div>';
  try {
    const res = await api().sensitivity({ ...S.values });
    if (!res.ok) { wrap.innerHTML = `<div class="sens-loading">${esc(res.error || "计算失败")}</div>`; return; }
    const lv = res.levels || ["-10%", "Base", "+10%"];
    const rows = res.rows || [];
    let html = '<thead><tr><th>' + biHtml("驱动因素", "Driver") + "</th>" +
      lv.map((l) => `<th>${esc(l)}</th>`).join("") + "</tr></thead><tbody>";
    rows.forEach((r) => {
      html += `<tr><td class="txt term">${biHtml(r.label, r.label_en || "")}</td>` +
        r.cells.map((c, i) => {
          const cls = i === 1 ? ' class="base-col"' : "";
          const mirrTxt = (c.mirr === undefined || isNaN(c.mirr))
            ? "—" : (c.mirr * 100).toFixed(2) + "%";
          const eqTxt = (c.eq_irr === undefined || isNaN(c.eq_irr))
            ? "—" : (c.eq_irr * 100).toFixed(2) + "%";
          return `<td${cls}>IRR ${(c.irr * 100).toFixed(2)}%<br>` +
                 `<span class="sub">Eq.IRR ${eqTxt}<br>MIRR ${mirrTxt}<br>` +
                 `NPV ${fmt(c.npv, 0)}<br>DSCR ${c.dscr.toFixed(2)}</span></td>`;
        }).join("") + "</tr>";
    });
    wrap.innerHTML = `<table class="data-table sens-table">${html}</tbody></table>
      <div id="term-sens" class="term-sens"><div class="sens-loading">借款期限敏感性计算中…</div></div>`;
    runTermSensitivity();
    $("table-hint").innerHTML = biHtml(
      "每个驱动因素单独 ±10% · 单位：万元 · 债务比例/利率只影响 Eq.IRR（全投资 IRR 与融资无关）；增值税率仅在「增值税免税年限 < 运营期」时生效。下表为借款期限敏感性（全投资 IRR 与期限无关）",
      "Each driver ±10% in isolation · 10K CNY · Debt drivers affect equity IRR only; VAT rate applies only when the VAT exemption is shorter than the operating period");
  } catch (e) {
    wrap.innerHTML = `<div class="sens-loading">${esc(String(e))}</div>`;
  }
}

function runScenarios() {
  api().scenarios({ ...S.values }).then((res) => {
    if (!res.ok) { toast(res.error, true); return; }
    const cols = ["情景", "全投资 IRR", "资本金 IRR", "全投资 NPV",
                  "资本金 NPV", "LCOE", "最小 DSCR", "回收期"];
    const colsEn = ["Scenario", "Project IRR", "Equity IRR", "Project NPV",
                    "Equity NPV", "LCOE", "Min DSCR", "Payback"];
    let html = "<thead><tr>" + cols.map((c, i) =>
      `<th>${biHtml(c, colsEn[i])}</th>`).join("") +
      "</tr></thead><tbody>";
    res.rows.forEach((r, i) => {
      const cls = i === 0 ? ' class="constr"' : "";
      html += `<tr${cls}>` +
        `<td><b>${biHtml(r.name, r.name_en)}</b></td>` +
        `<td>${r.pirr}</td><td>${r.eirr}</td>` +
        `<td>${r.npv}</td><td>${r.enpv}</td>` +
        `<td>${r.lcoe}</td><td>${r.dscr}</td><td>${r.payback}</td></tr>`;
    });
    $("scen-table").innerHTML = html + "</tbody>";
  });
}

/* ── 图表 ─────────────────────────────────────────────── */
const NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs, text) {
  const e = document.createElementNS(NS, tag);
  if (attrs) Object.entries(attrs).forEach(([k, v]) => e.setAttribute(k, v));
  if (text != null) e.textContent = text;
  return e;
}

function fmtNum(v) {
  const a = Math.abs(v);
  if (a >= 10000) return (v / 10000).toFixed(a >= 100000 ? 0 : 1) + "亿";
  return Math.round(v).toLocaleString("zh-CN");
}

function fmt(v, nd) {
  if (v == null || !isFinite(v)) return "—";
  return v.toLocaleString("zh-CN", {
    minimumFractionDigits: nd,
    maximumFractionDigits: nd,
  });
}

function makeChart(host, opts) {
  host.innerHTML = "";
  const W = Math.max(380, host.clientWidth || 520);
  const H = Math.round(W * 0.37);
  const P = { l: 56, r: 12, t: 14, b: 26 };
  const labels = opts.labels;
  const n = labels.length;
  const stepX = n > 1 ? (W - P.l - P.r) / (n - 1) : 0;
  const xAt = (i) => P.l + (n > 1 ? stepX * i : (W - P.l - P.r) / 2);

  let vals = [0];
  opts.series.forEach((s) => s.values.forEach((v) => { if (v != null) vals.push(v); }));
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.08;
  lo -= pad; hi += pad;
  const yAt = (v) => P.t + (H - P.t - P.b) * (1 - (v - lo) / (hi - lo));

  const svg = svgEl("svg", {
    viewBox: `0 0 ${W} ${H}`,
    role: "img",
  });

  const defs = svgEl("defs");
  const grad = svgEl("linearGradient", { id: "areaGreen", x1: "0", y1: "0", x2: "0", y2: "1" });
  grad.append(
    svgEl("stop", { offset: "0%", "stop-color": "#27ae60", "stop-opacity": "0.18" }),
    svgEl("stop", { offset: "100%", "stop-color": "#27ae60", "stop-opacity": "0" }),
  );
  defs.appendChild(grad);
  svg.appendChild(defs);

  // 建设期底色
  if (opts.shadeUntil > 0) {
    const x0 = P.l - stepX / 2;
    const x1 = xAt(Math.min(opts.shadeUntil - 1, n - 1)) + stepX / 2;
    svg.appendChild(svgEl("rect", {
      x: Math.max(P.l - stepX / 2, x0), y: P.t,
      width: Math.max(0, x1 - x0), height: H - P.t - P.b,
      fill: "#eef4fa",
    }));
    svg.appendChild(svgEl("text", {
      x: Math.max(P.l, x0) + 5, y: P.t + 12,
      "font-size": "10.5", fill: "#30353a",
    }, "建设期 Construction"));
  }

  // 网格与 Y 轴
  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const v = lo + (hi - lo) * (i / ticks);
    const y = yAt(v);
    svg.appendChild(svgEl("line", {
      x1: P.l, y1: y, x2: W - P.r, y2: y,
      stroke: "#e8eef5", "stroke-width": "1",
    }));
    svg.appendChild(svgEl("text", {
      x: P.l - 8, y: y + 3.5, "text-anchor": "end",
      "font-size": "10.5", fill: "#2c3136",
    }, fmtNum(v)));
  }
  // 零轴
  if (lo < 0 && hi > 0) {
    svg.appendChild(svgEl("line", {
      x1: P.l, y1: yAt(0), x2: W - P.r, y2: yAt(0),
      stroke: "#c9d6e3", "stroke-dasharray": "3 3",
    }));
  }

  // X 轴标签
  const every = Math.max(1, Math.ceil(n / 8));
  const lastTick = Math.floor((n - 1) / every) * every;
  const showLast = n - 1 - lastTick >= Math.max(2, every * 0.6);
  labels.forEach((lab, i) => {
    if (i % every !== 0 && !(i === n - 1 && showLast)) return;
    svg.appendChild(svgEl("text", {
      x: xAt(i), y: H - 8, "text-anchor": "middle",
      "font-size": "10.5", fill: "#2c3136",
    }, String(lab)));
  });

  // 面积（第一条线）
  if (opts.series[0] && opts.series[0].fill !== false) {
    const s = opts.series[0];
    let d = `M ${xAt(0)} ${yAt(0)}`;
    s.values.forEach((v, i) => { d += ` L ${xAt(i)} ${yAt(v)}`; });
    d += ` L ${xAt(n - 1)} ${yAt(0)} Z`;
    svg.appendChild(svgEl("path", { d, fill: "url(#areaGreen)" }));
  }

  // 折线
  opts.series.forEach((s) => {
    let d = "";
    s.values.forEach((v, i) => {
      d += (i === 0 ? "M " : " L ") + xAt(i) + " " + yAt(v);
    });
    svg.appendChild(svgEl("path", {
      d, fill: "none", stroke: s.color, "stroke-width": "2",
      "stroke-linejoin": "round", "stroke-linecap": "round",
      "stroke-dasharray": s.dashed ? "5 3" : "none",
    }));
    s.values.forEach((v, i) => {
      const c = svgEl("circle", {
        cx: xAt(i), cy: yAt(v), r: "2.4",
        fill: "#fff", stroke: s.color, "stroke-width": "1.6",
      });
      c.appendChild(svgEl("title", {}, `第 ${labels[i]} 年 Year ${labels[i]} · ${s.name}：${fmt(v, 1)} 万元`));
      svg.appendChild(c);
    });
  });

  host.appendChild(svg);
}

function makeBarChart(host, opts) {
  host.innerHTML = "";
  const W = Math.max(380, host.clientWidth || 520);
  const H = Math.round(W * 0.37);
  const P = { l: 56, r: 12, t: 14, b: 26 };
  const n = opts.labels.length;

  const vals = [0];
  opts.series.forEach((s) => s.values.forEach((v) => { if (v != null) vals.push(v); }));
  let hi = Math.max(...vals) * 1.06;
  const lo = 0;
  const yAt = (v) => P.t + (H - P.t - P.b) * (1 - (v - lo) / (hi - lo));
  const groupW = (W - P.l - P.r) / n;
  const barW = Math.max(2, groupW * 0.32);

  const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}` });

  if (opts.shadeUntil > 0) {
    svg.appendChild(svgEl("rect", {
      x: P.l, y: P.t, width: groupW * opts.shadeUntil,
      height: H - P.t - P.b, fill: "#eef4fa",
    }));
  }

  const ticks = 4;
  for (let i = 0; i <= ticks; i++) {
    const v = hi * (i / ticks);
    const y = yAt(v);
    svg.appendChild(svgEl("line", {
      x1: P.l, y1: y, x2: W - P.r, y2: y,
      stroke: "#e8eef5", "stroke-width": "1",
    }));
    svg.appendChild(svgEl("text", {
      x: P.l - 8, y: y + 3.5, "text-anchor": "end",
      "font-size": "10.5", fill: "#2c3136",
    }, fmtNum(v)));
  }

  const every = Math.max(1, Math.ceil(n / 8));
  const lastTick = Math.floor((n - 1) / every) * every;
  const showLast = n - 1 - lastTick >= Math.max(2, every * 0.6);
  opts.labels.forEach((lab, i) => {
    if (i % every !== 0 && !(i === n - 1 && showLast)) return;
    const x = P.l + groupW * (i + 0.5);
    svg.appendChild(svgEl("text", {
      x, y: H - 8, "text-anchor": "middle",
      "font-size": "10.5", fill: "#2c3136",
    }, String(lab)));
  });

  opts.labels.forEach((lab, i) => {
    const cx = P.l + groupW * (i + 0.5);
    opts.series.forEach((s, si) => {
      const v = s.values[i] || 0;
      const off = (si - (opts.series.length - 1) / 2) * (barW + 1.5);
      const x = cx + off - barW / 2;
      const y = yAt(Math.max(0, v));
      const h = Math.max(1, yAt(0) - y);
      const r = svgEl("rect", {
        x, y, width: barW, height: h, rx: "1.6", fill: s.color, opacity: "0.92",
      });
      r.appendChild(svgEl("title", {}, `第 ${lab} 年 Year ${lab} · ${s.name}：${fmt(v, 1)} 万元`));
      svg.appendChild(r);
    });
  });

  host.appendChild(svg);
}


/* 图表标题、图例等静态双语节点：记录中文源，按主/副语言重绘 */
function biText(cn, en) {
  const main = pickText(cn, en, "main");
  const sub = pickText(cn, en, "sub");
  return esc(main) + (sub && sub !== main ? "  " + esc(sub) : "");
}

function applyBiStatic(root) {
  (root || document).querySelectorAll(".panel-head h3, .legend span").forEach((el) => {
    const enSpan = el.querySelector(".en");
    if (!enSpan) return;
    if (!el.dataset.cn) el.dataset.cn = el.textContent.replace(enSpan.textContent, "").trim();
    el.innerHTML = biHtml(el.dataset.cn, enSpan.textContent);
  });
}

function renderCharts(c) {
  makeChart($("chart-cum"), {
    labels: c.yr,
    shadeUntil: c.t,
    series: [
      { name: biText("全投资", "Project"), color: "#27ae60", values: c.cum_p },
      { name: biText("资本金", "Equity"), color: "#2980b9", values: c.cum_e, dashed: true, fill: false },
    ],
  });
  makeBarChart($("chart-flow"), {
    labels: c.yr,
    shadeUntil: c.t,
    series: [
      { name: biText("营业收入", "Revenue"), color: "#27ae60", values: c.revenue },
      { name: biText("经营成本", "OpEx"), color: "#e67e22", values: c.opex },
    ],
  });
}

/* ── WACC 联网数据 ────────────────────────────────────── */
function renderWaccChip(res) {
  const chip = $("wacc-chip");
  const txt = $("wacc-chip-text");
  if (!chip || !txt) return;
  const info = (S.model && S.model.waccInfo) || null;
  if (!res || !res.ok) {
    chip.className = "wacc-chip offline";
    txt.textContent = info
      ? `WACC ${(info.wacc * 100).toFixed(2)}%` : "WACC 离线 Offline";
    chip.title = "未能读取 WACC 数据 Unable to read WACC data";
    return;
  }
  const kind = res.source === "live" ? "live"
             : res.source === "cache" ? "cache" : "offline";
  chip.className = "wacc-chip " + kind;
  txt.textContent = info
    ? `WACC ${(info.wacc * 100).toFixed(2)}% · ` +
      (kind === "live" ? "实时 Live" : kind === "cache" ? "快照 Snapshot" : "基准 Base")
    : (kind === "live" ? "WACC 实时 Live"
       : kind === "cache" ? "WACC 快照 Snapshot" : "WACC 基准 Base");
  chip.title = [
    "来源 Source：" + (kind === "live" ? "联网实时 Live" : kind === "cache" ? "本地快照 Snapshot" : "内置兜底 Fallback"),
    info ? `国别 ${info.country} · 行业 ${info.sector}` : "",
    info ? `币种 ${info.ccy} · Rf ${(info.rf * 100).toFixed(3)}%` : "",
    info ? `βu ${info.betaU.toFixed(4)} · ERP ${(info.erp * 100).toFixed(2)}%` : "",
    info ? `CRP ${(info.crp * 100).toFixed(2)}% · 违约利差 ${(info.cds * 100).toFixed(2)}%` : "",
    info ? `信用利差 ${(info.creditSpread * 100).toFixed(2)}% · Rd ${(info.rd * 100).toFixed(2)}%` : "",
    res.asof ? `数据日期 ${res.asof}` : "",
    res.fetched_at ? `抓取时间 ${res.fetched_at}` : "",
    res.error ? `提示：${res.error}` : "",
  ].filter(Boolean).join("\n");
}

async function refreshWacc(force, auto) {
  if (S.waccBusy) return;                 // 上一次联网尚未返回，避免叠加
  S.waccBusy = true;
  if (force) S.waccCheckedAt = Date.now();
  if (force && !auto) setStatus(T("联网刷新 WACC…"), "busy");
  try {
    const res = await api().wacc_data(!!force);
    S.waccLive = res;
    if (force && res && res.ok && res.source === "live") {
      S.waccFetchedAt = Date.now();
    }
    if (force && res && res.ok) {
      await refreshFieldOptions();
      if (S.model) compute();
    }
    renderWaccChip(res);
    if (force && !auto) {
      if (res && res.ok) {
        setStatus(T("WACC 已刷新"));
        toast(T("WACC 数据已更新，模型已按所选币种口径重算"));
      } else {
        setStatus(T("WACC 刷新失败"), "err");
        toast(T("WACC 联网刷新失败，继续使用现有数据"), true);
      }
    }
  } catch (e) {
    renderWaccChip(null);
    if (!auto) {
      setStatus(T("WACC 刷新失败"), "err");
      toast(T("WACC 获取失败") + "：" + e, true);
    }
  } finally {
    S.waccBusy = false;
  }
}

/* ── 导出 / 状态 / 提示 ───────────────────────────────── */
const EXPORT_EN = {
  "参数": "Parameters", "核心指标": "Key Metrics", "损益表": "Income Statement",
  "全部投资现金流": "Project Cash Flow", "资本金现金流": "Equity Cash Flow",
  "还本付息表": "Debt Service", "销售收入": "Revenue",
  "资产负债表": "Balance Sheet", "总成本表": "Total Costs",
  "资金筹措": "Funding", "折旧表": "Depreciation", "摊销表": "Amortisation",
  "财务计划": "Financial Plan", "决策信息模版": "Decision Template",
  "增值税计算表": "VAT Calculation", "术语表": "Glossary",
  "LCOE计算表": "LCOE Calculation", "WACC计算表": "WACC Calculation",
};
const EXPORT_LANG_NAME = {
  bi: "中英对照 Bilingual", en: "English",
  "zh-CN": "简体中文 Simplified", "zh-TW": "繁體中文 Traditional",
};

// 导出语言＝界面语言：主语言 + 副语言；副语言为「无」时导出单语版
function exportLang() {
  return "pair";
}

function uiLangText(key) {
  const sel = document.querySelector(`.field[data-key="${key}"] select`);
  if (!sel) return "";
  const o = sel.options[sel.selectedIndex];
  return o ? String(o.textContent || "").trim() : "";
}

function isNoneLang(txt) {
  return !txt || /^(无|なし|없음|無し)/.test(txt) || /none/i.test(txt);
}

function syncExportLang() {
  const el = $("export-langnow");
  if (!el) return;
  const a = uiLangText("ui_lang");
  const b = uiLangText("ui_lang2");
  el.textContent = isNoneLang(b) ? a : `${a}  +  ${b}`;
}

function buildExportList() {
  const box = $("export-tables");
  if (!box || !S.schema) return;
  const names = ["参数", "核心指标"].concat(S.schema.tables.map((t) => t.name));
  box.innerHTML = names.map((n) => {
    const en = EXPORT_EN[n] || n;
    const sub = pickText(n, en, "sub") || "";
    // tab 名恒为英文；副行随「副语言」显示（中文界面显示中文名）
    const strong = langCode() === "zh" || langCode() === "zh-CN" || langCode() === "zh-TW" ? n : en;
    const tail = sub && sub !== strong ? sub : "";
    return `<button type="button" class="export-item" data-table="${n}">` +
      `<strong>${esc(strong)}</strong>${tail ? `<span>${esc(tail)}</span>` : ""}</button>`;
  }).join("");
}

// 导出弹窗里的固定文案：按主/副语言渲染
function localizeExportDialog() {
  const set = (sel, cn, en) => { const el = $(sel); if (el) el.innerHTML = biHtml(cn, en); };
  set("export-title", "导出 Excel", "Export to Excel");
  const btn = $("export-all");
  if (btn) btn.innerHTML = `<span>${biHtml("下载全部表格", "All 16 tables · one file, one tab each")}</span>` +
                           `<span class="export-arrow">↓</span>`;
  set("export-close", "关闭", "Close");
  const k = document.querySelector(".export-now-k");
  if (k) k.innerHTML = biHtml("导出语言", "Export language");
  const tip = document.querySelector(".export-now-tip");
  if (tip) tip.innerHTML = biHtml("跟随界面主／副语言；副语言选「无」则导出单语版",
                                  "Follows the primary/secondary UI languages; choose \u201CNone\u201D for a single-language file");
  const hint = document.querySelector(".export-hint");
  if (hint) hint.innerHTML = biHtml(
    "每张表独立一个 tab；文件名与 tab 名统一为英文。导出内容与界面语言一致（主语言在上、副语言在下）；主语言为中文时货币用万元，其他语言按 k 显示（1 万元 = 10 k）。",
    "One tab per table; file and tab names are always English. Content follows the UI languages (primary on top, secondary below); Chinese uses 10k CNY, other languages use k (1 unit of 10k = 10 k).");
}

function openExport() {
  localizeExportDialog();
  buildExportList();
  syncExportLang();
  $("export-gate").classList.remove("hidden");
}

function closeExport() {
  $("export-gate").classList.add("hidden");
}

async function downloadExport(tables) {
  const lang = exportLang();
  setStatus(T("导出中…"), "busy");
  try {
    const res = await api().export(lang, tables || null);
    if (res.gated) { LicenseUI.showGate(res.license); return; }
    if (res.ok) {
      setStatus(T("导出完成"));
      toast(T("已导出") + "：" + res.path);
    } else if (res.cancelled) {
      setStatus(T("已取消导出"));
    } else {
      setStatus(T("导出失败"), "err");
      toast(res.error, true);
    }
  } catch (e) {
    setStatus(T("导出失败"), "err");
    toast(String(e), true);
  }
}

function setStatus(msg, kind) {
  const el = $("status");
  el.className = "status" + (kind ? " " + kind : "");
  el.innerHTML = "<i></i>" + msg;
}

let toastTimer = null;
function toast(msg, isErr) {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast show" + (isErr ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = "toast"; }, 3600);
}

/* ── 事件绑定 ─────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
  $("btn-calc").addEventListener("click", compute);
  $("btn-export").addEventListener("click", openExport);
  $("export-close").addEventListener("click", closeExport);
  $("export-all").addEventListener("click", () => downloadExport(null));
  $("export-gate").addEventListener("click", (e) => {
    if (e.target === $("export-gate")) closeExport();
  });
  $("export-langs").addEventListener("change", syncExportLang);
  $("export-tables").addEventListener("click", (e) => {
    const btn = e.target.closest(".export-item");
    if (btn) downloadExport([btn.dataset.table]);
  });
  $("btn-reset").addEventListener("click", async () => {
    const res = await api().defaults();
    S.decEdits = {};
    setValues(res.values);
    compute();
  });
  $("btn-scen").addEventListener("click", runScenarios);
  $("btn-wacc").addEventListener("click", () => refreshWacc(true, false));

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeExport(); return; }
    if (!e.metaKey) return;
    if (e.key === "r") { e.preventDefault(); compute(); }
    if (e.key === "s") { e.preventDefault(); openExport(); }
  });

  let rz = null;
  window.addEventListener("resize", () => {
    clearTimeout(rz);
    rz = setTimeout(() => {
      if (!S.model) return;
      if (S.view === "overview") renderCharts(S.model.chart);
      else if (S.view.startsWith("table:")) renderTable(S.table);
    }, 180);
  });
});

window.__rneCompute = compute;
