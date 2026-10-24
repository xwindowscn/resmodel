/* T-202610-010 P2 · 体验版外壳：10 分钟全功能 → 16 项可调；导出全程关闭；语言不锁 */
(function () {
  "use strict";

  const TRIAL_MS = 10 * 60 * 1000;
  const K_END = "resmodel_demo_end_v1";
  const K_SEEN = "resmodel_demo_locked_notice_v1";

  // 体验模式可编辑的 16 项（app 结构键名）
  const WHITELIST = new Set([
    // 规模与发电
    "cap_dc_mw", "cap_ac_mw", "actual_gen_hours", "first_year_haircut",
    // 电价与收入
    "benchmark_tariff", "market_price", "market_trade_hours", "storage_elec_price",
    // 投资与储能
    "epc_price_station", "storage_ratio", "storage_duration", "storage_unit_price",
    // 融资与汇率
    "debt_ratio", "debt_rate", "debt_tenor", "exchange_rate",
  ]);
  // 语言与显示币种永远不锁
  const EXEMPT = new Set(["ui_lang", "ui_lang2", "display_ccy"]);

  let endAt = 0;
  let locked = false;
  let timer = null;

  const $ = (id) => document.getElementById(id);

  /* ── 计时 ── */
  function loadEnd() {
    let v = 0;
    try { v = parseInt(localStorage.getItem(K_END) || "0", 10) || 0; } catch (e) {}
    if (!v) {
      v = Date.now() + TRIAL_MS;
      try { localStorage.setItem(K_END, String(v)); } catch (e) {}
    }
    return v;
  }

  function fmt(ms) {
    if (ms < 0) ms = 0;
    const s = Math.ceil(ms / 1000);
    return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
  }

  /* ── 顶栏 ── */
  function makeBar() {
    const bar = document.createElement("div");
    bar.id = "demo-bar";
    bar.innerHTML =
      '<span class="db-chip" id="db-chip">体验版 · 全功能剩余 <b id="db-time">--:--</b></span>' +
      '<span class="db-note" id="db-note">10 分钟内可改全部参数，不可导出</span>' +
      '<a class="db-buy" href="https://resmodel.com/#pricing" target="_blank" rel="noopener">购买正式版 →</a>';
    document.body.appendChild(bar);
    const st = document.createElement("style");
    st.textContent = `
#demo-bar{position:fixed;top:10px;right:14px;z-index:9999;display:flex;align-items:center;gap:10px;
  background:rgba(255,255,255,.96);border:1px solid #d7e2ee;border-radius:999px;padding:6px 12px;
  box-shadow:0 4px 16px rgba(20,55,90,.10);font-size:12.5px;color:#22414d;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
#demo-bar .db-chip{font-weight:600;color:#1F4E79}
#demo-bar .db-chip b{font-variant-numeric:tabular-nums;color:#0d7c3f}
#demo-bar.locked .db-chip{color:#a3541b}
#demo-bar.locked .db-chip b{color:#a3541b}
#demo-bar .db-note{color:#6b8397}
#demo-bar .db-buy{color:#fff;background:#1F4E79;border-radius:999px;padding:3px 10px;text-decoration:none;font-weight:600}
.demo-locked{opacity:.55}
.demo-locked input,.demo-locked select{background:#eef2f6!important;cursor:not-allowed}
.demo-locked::after{content:"🔒";position:absolute;right:6px;top:50%;transform:translateY(-50%);font-size:10px;opacity:.6}
.field{position:relative}
#demo-modal{position:fixed;inset:0;z-index:100000;display:flex;align-items:center;justify-content:center;
  background:rgba(8,22,36,.5);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
#demo-modal .dm{background:#fff;border-radius:14px;max-width:520px;padding:26px 28px;color:#16324f;line-height:1.75}
#demo-modal h3{margin:0 0 10px;font-size:18px}
#demo-modal p{margin:8px 0;font-size:14px}
#demo-modal .acts{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}
#demo-modal a,#demo-modal button{font-family:inherit;font-size:13.5px;padding:9px 16px;border-radius:8px;border:1px solid #c8d6e5;
  background:#f0f4f8;color:#22414d;text-decoration:none;cursor:pointer}
#demo-modal a.primary,#demo-modal button.primary{background:#1F4E79;color:#fff;border-color:#1F4E79}
`;
    document.head.appendChild(st);
  }

  /* ── 锁定 ── */
  function applyLock() {
    const rows = document.querySelectorAll(".field[data-key]");
    rows.forEach((row) => {
      const k = row.dataset.key;
      const shouldLock = locked && !WHITELIST.has(k) && !EXEMPT.has(k);
      row.classList.toggle("demo-locked", shouldLock);
      row.querySelectorAll("input,select,textarea").forEach((el) => {
        if (shouldLock) {
          if (el.dataset.demoLocked !== "1") {
            el.dataset.demoLocked = "1";
            el.dataset.prevDisabled = el.disabled ? "1" : "0";
          }
          el.disabled = true;
        } else if (el.dataset.demoLocked === "1") {
          el.disabled = el.dataset.prevDisabled === "1";
          delete el.dataset.demoLocked;
          delete el.dataset.prevDisabled;
        }
      });
    });
    document.querySelectorAll("#table-wrap input, #table-wrap select, #table-wrap textarea").forEach((el) => {
      if (locked) {
        if (el.dataset.demoLocked !== "1") {
          el.dataset.demoLocked = "1";
          el.dataset.prevDisabled = el.disabled ? "1" : "0";
        }
        el.disabled = true;
      } else if (el.dataset.demoLocked === "1") {
        el.disabled = el.dataset.prevDisabled === "1";
        delete el.dataset.demoLocked;
        delete el.dataset.prevDisabled;
      }
    });
    if (locked) {
      document.querySelectorAll("#presets button, .preset-bar button, .segmented button").forEach((b) => {
        if (b.dataset && b.dataset.demoKeep) return;
        b.disabled = true;
      });
    }
  }

  function observe() {
    const target = document.querySelector(".sidebar") || document.body;
    let pending = false;
    new MutationObserver(() => {
      if (pending) return;
      pending = true;
      setTimeout(() => { pending = false; applyLock(); }, 0);
    }).observe(target, { childList: true, subtree: true });
  }

  /* ── 结束提示 ── */
  function showLockedModal() {
    let seen = false;
    try { seen = localStorage.getItem(K_SEEN) === "1"; } catch (e) {}
    if (seen) return;
    try { localStorage.setItem(K_SEEN, "1"); } catch (e) {}
    const m = document.createElement("div");
    m.id = "demo-modal";
    m.innerHTML = `<div class="dm">
      <h3>10 分钟全功能体验已结束</h3>
      <p>现在进入<b>体验模式</b>：仍可修改 <b>16 项</b>关键参数（装机、发电小时、电价、储能、EPC 单价、融资与汇率），其余参数锁定，全部报表继续实时重算。</p>
      <p style="color:#6b8397;font-size:13px">The 10-minute full trial has ended. Sixteen key assumptions remain editable; everything else is locked and all statements keep recalculating live.</p>
      <div class="acts">
        <button class="primary" id="dm-ok">继续体验</button>
        <a href="https://resmodel.com/#pricing" target="_blank" rel="noopener">查看正式版</a>
      </div></div>`;
    document.body.appendChild(m);
    m.querySelector("#dm-ok").onclick = () => m.remove();
    m.addEventListener("click", (e) => { if (e.target === m) m.remove(); });
  }

  function tick() {
    const left = endAt - Date.now();
    const t = $("db-time"), chip = $("db-chip"), note = $("db-note"), bar = $("demo-bar");
    if (left <= 0) {
      if (!locked) {
        locked = true;
        window.__EXPORT_BLOCKED__ = true;
        window.__EXPORT_BLOCKED_MSG__ = "体验版不可导出，正式版可导出 Excel";
        if (bar) bar.classList.add("locked");
        if (chip) chip.innerHTML = "体验模式 · 16 项可调";
        if (note) note.textContent = "其余参数已锁定 · 不可导出";
        applyLock();
        showLockedModal();
      }
      if (timer) { clearInterval(timer); timer = null; }
      return;
    }
    if (t) t.textContent = fmt(left);
  }

  function start() {
    endAt = loadEnd();
    locked = endAt <= Date.now();
    // 体验版全程不可导出（业主要求：首次 10 分钟也不可导出）
    window.__EXPORT_BLOCKED__ = true;
    window.__EXPORT_BLOCKED_MSG__ = "体验版不可导出，正式版可导出 Excel";
    makeBar();
    const chip = $("license-chip");
    if (chip) chip.style.display = "none";
    const t = $("app-title");
    if (t && !/Demo/.test(t.textContent)) t.textContent += "（体验版 Demo）";
    if (locked) {
      const bar = $("demo-bar");
      if (bar) bar.classList.add("locked");
      const c = $("db-chip");
      if (c) c.innerHTML = "体验模式 · 16 项可调";
      const n = $("db-note");
      if (n) n.textContent = "其余参数已锁定 · 不可导出";
      showLockedModal();
    } else {
      timer = setInterval(tick, 500);
      tick();
    }
    applyLock();
    observe();
    // 锁定状态在语言切换重建后也要保持
    setInterval(applyLock, 1500);
  }

  function waitForApp() {
    if (document.querySelector(".sidebar .field[data-key]")) { start(); return; }
    let n = 0;
    const iv = setInterval(() => {
      if (document.querySelector(".sidebar .field[data-key]") || ++n > 400) {
        clearInterval(iv);
        if (n <= 400) start();
      }
    }, 100);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", waitForApp);
  else waitForApp();
})();
