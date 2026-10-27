/* T-202610-010 P2 · 体验版外壳：20 分钟全功能 → 16 项可调；导出全程关闭；语言不锁 */
(function () {
  "use strict";

  const TRIAL_SECONDS = 720;          // 体验版：每台设备每天 12 分钟
  const TRIAL_MS = TRIAL_SECONDS * 1000;
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
  let LICENSED = false;
  let DEVICE_HASH = "";
  let SERVER_USED = null;             // 服务端累计试用秒数（D1 trial_used_seconds）
  let lastBeat = Date.now();
  const LICENSE_BASE = "https://license.resmodel.com";

  const $ = (id) => document.getElementById(id);

  /* ── 计时 ── */
  function loadEnd() {
    // 按"天"重置：同一台设备每天各有 TRIAL_SECONDS 秒完整体验
    const today = new Date().toISOString().slice(0, 10);
    let v = 0, day = "";
    try {
      v = parseInt(localStorage.getItem(K_END) || "0", 10) || 0;
      day = localStorage.getItem(K_END + "_day") || "";
    } catch (e) {}
    if (!v || day !== today) {
      v = Date.now() + TRIAL_MS;
      try {
        localStorage.setItem(K_END, String(v));
        localStorage.setItem(K_END + "_day", today);
      } catch (e) {}
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
      '<span class="db-note" id="db-note">每天 12 分钟内可改全部参数，不可导出</span>' +
      '<button type="button" class="db-code" id="db-code-btn">机器码</button>' +
      '<a class="db-buy" href="https://resmodel.com/#pricing" target="_blank" rel="noopener">购买正式版 →</a>';
    document.body.appendChild(bar);
    const st = document.createElement("style");
    st.textContent = `
#demo-bar{position:fixed;bottom:14px;left:50%;transform:translateX(-50%);z-index:99999;display:flex;align-items:center;gap:10px;
  background:rgba(255,255,255,.96);border:1px solid #d7e2ee;border-radius:999px;padding:6px 12px;
  box-shadow:0 4px 16px rgba(20,55,90,.10);font-size:12.5px;color:#22414d;
  font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
#demo-bar .db-chip{font-weight:600;color:#1F4E79}
#demo-bar .db-chip b{font-variant-numeric:tabular-nums;color:#0d7c3f}
#demo-bar.locked .db-chip{color:#a3541b}
#demo-bar.locked .db-chip b{color:#a3541b}
#demo-bar .db-note{color:#6b8397}
#demo-bar .db-buy{color:#fff;background:#1F4E79;border-radius:999px;padding:3px 10px;text-decoration:none;font-weight:600}
#demo-bar .db-code{font-family:inherit;font-size:12.5px;padding:3px 10px;border-radius:999px;border:1px solid #c8d6e5;background:#fff;color:#22414d;cursor:pointer}
#demo-code-panel{position:fixed;bottom:64px;left:50%;transform:translateX(-50%);z-index:100000;width:min(430px,92vw);
  background:#fff;border:1px solid #d7e2ee;border-radius:14px;box-shadow:0 16px 44px rgba(20,55,90,.18);
  padding:18px 20px;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;color:#16324f;line-height:1.7}
#demo-code-panel h4{margin:0 0 8px;font-size:15px}
#demo-code-panel .code{font-family:ui-monospace,Menlo,monospace;font-size:19px;letter-spacing:.06em;
  background:#f4f7fa;border:1px dashed #b9cada;border-radius:10px;padding:10px 12px;text-align:center;user-select:all}
#demo-code-panel .hint{font-size:12.5px;color:#6b8397;margin:10px 0}
#demo-code-panel .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
#demo-code-panel button{font-family:inherit;font-size:12.5px;padding:6px 12px;border-radius:8px;border:1px solid #c8d6e5;background:#f0f4f8;cursor:pointer}
#demo-code-panel button.primary{background:#1F4E79;color:#fff;border-color:#1F4E79}
#demo-code-panel .st{font-size:12.5px;margin-top:10px;color:#2e6b47}
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
      const shouldLock = locked && !LICENSED && !WHITELIST.has(k) && !EXEMPT.has(k);
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
    document.querySelectorAll("#presets button, .preset-bar button, .segmented button").forEach((b) => {
      if (b.dataset && b.dataset.demoKeep) return;
      b.disabled = locked && !LICENSED;
    });
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
      <h3>20 分钟全功能体验已结束</h3>
      <p>现在进入<b>体验模式</b>：仍可修改 <b>16 项</b>关键参数（装机、发电小时、电价、储能、EPC 单价、融资与汇率），其余参数锁定，全部报表继续实时重算。</p>
      <p style="color:#6b8397;font-size:13px">The 12-minute daily trial has ended. Sixteen key assumptions remain editable; everything else is locked and all statements keep recalculating live.</p>
      <div class="acts">
        <button class="primary" id="dm-ok">继续体验</button>
        <a href="https://resmodel.com/#pricing" target="_blank" rel="noopener">查看正式版</a>
      </div></div>`;
    document.body.appendChild(m);
    m.querySelector("#dm-ok").onclick = () => m.remove();
    m.addEventListener("click", (e) => { if (e.target === m) m.remove(); });
  }


  /* ── 授权：机器码（客户点按钮显示，管理员按码开通） ── */
  function codeOf(hash) {
    const h = String(hash || "").slice(0, 16).toUpperCase();
    return h.replace(/(.{4})/g, "$1-").replace(/-$/, "");
  }
  async function sha256Hex(str) {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(str));
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
  }
  function fingerprint() {
    let gl = "";
    try {
      const c = document.createElement("canvas");
      const g = c.getContext("webgl");
      const d = g.getExtension("WEBGL_debug_renderer_info");
      gl = [g.getParameter(d.UNMASKED_VENDOR_WEBGL), g.getParameter(d.UNMASKED_RENDERER_WEBGL)].join("|");
    } catch (e) {}
    let cv = "";
    try {
      const c = document.createElement("canvas");
      c.width = 220; c.height = 40;
      const g = c.getContext("2d");
      g.textBaseline = "top"; g.font = "14px Arial";
      g.fillStyle = "#f60"; g.fillRect(0, 0, 100, 20);
      g.fillStyle = "#069"; g.fillText("resmodel-fp", 2, 2);
      cv = c.toDataURL().slice(-96);
    } catch (e) {}
    return [
      navigator.userAgent, navigator.language, navigator.platform,
      navigator.hardwareConcurrency || 0, screen.width + "x" + screen.height + "x" + screen.colorDepth,
      Intl.DateTimeFormat().resolvedOptions().timeZone || "", cv, gl,
    ].join("~");
  }
  async function post(path, body) {
    const r = await fetch(LICENSE_BASE + path, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify(body), cache: "no-store",
    });
    return await r.json();
  }
  async function fetchT(url, ms) {
    const ctl = new AbortController();
    const t = setTimeout(() => ctl.abort(), ms || 900);
    try { return await fetch(url, { signal: ctl.signal, cache: "no-store", mode: "cors" }); }
    finally { clearTimeout(t); }
  }

  // 本机握手：同机装了已授权 app 时，网页免输入直接可用，且与 app 共用一个机器码
  async function tryHandshake() {
    for (let port = 47653; port < 47661; port++) {
      try {
        const r = await fetchT("http://127.0.0.1:" + port + "/handshake", 900);
        if (!r.ok) continue;
        const d = await r.json();
        if (!d || d.v !== 1) continue;
        if (d.device_hash) DEVICE_HASH = d.device_hash;
        if (d.token) {
          const v = await post("/v1/verify", { token: d.token });
          if (v && v.ok && v.state) { applyState(v); return true; }
        }
        return true;
      } catch (e) {}
    }
    return false;
  }

  async function ensureDevice() {
    if (DEVICE_HASH) return true;

    try {
      DEVICE_HASH = await sha256Hex("resmodel-web:" + fingerprint());
      const r = await post("/v1/register", { device_hash: DEVICE_HASH, app_version: "web-demo", origin: "web" });
      applyState(r);
      return true;
    } catch (e) { return false; }
  }
  async function heartbeat() {
    if (!DEVICE_HASH) { await ensureDevice(); return; }
    try {
      const r = await post("/v1/heartbeat", { device_hash: DEVICE_HASH, elapsed_ms: Date.now() - lastBeat });
      lastBeat = Date.now();
      applyState(r);
    } catch (e) {}
  }
  function applyState(res) {
    const st = res && res.state;
    if (!st) return;
    if (typeof st.trial_used === "number") SERVER_USED = st.trial_used;
    if (st.licensed) unlock(st.license);
    else if (usedSeconds() >= TRIAL_SECONDS && !locked) forceLock();
  }

  function usedSeconds() {
    const local = endAt ? Math.max(0, Math.round((Date.now() - (endAt - TRIAL_MS)) / 1000)) : 0;
    if (SERVER_USED === null) return local;
    return Math.max(SERVER_USED, Math.min(local, SERVER_USED + 120)); // 离线时最多多算 2 分钟
  }

  function forceLock() {
    locked = true;
    window.__EXPORT_BLOCKED__ = true;
    if (timer) { clearInterval(timer); timer = null; }
    const bar = document.getElementById("demo-bar");
    if (bar) bar.classList.add("locked");
    const chip = document.getElementById("db-chip");
    if (chip) chip.textContent = "体验模式 · 16 项可调";
    const note = document.getElementById("db-note");
    if (note) note.textContent = "其余参数已锁定 · 不可导出";
    applyLock();
    showLockedModal();
  }
  function unlock(lic) {
    if (LICENSED) return;
    LICENSED = true;
    locked = false;
    window.__EXPORT_BLOCKED__ = false;
    window.__EXPORT_BLOCKED_MSG__ = "";
    if (timer) { clearInterval(timer); timer = null; }
    const bar = document.getElementById("demo-bar");
    const chip = document.getElementById("db-chip");
    const note = document.getElementById("db-note");
    if (bar) bar.classList.remove("locked");
    const exp = lic && lic.expires_at ? new Date(lic.expires_at * 1000).toLocaleDateString("zh-CN") : "永久";
    if (chip) chip.textContent = "已授权 · " + exp;
    if (note) note.textContent = "正式版已解锁 · 可导出";
    applyLock();
    const x = document.getElementById("demo-code-panel");
    if (x) x.remove();
  }

  function showCodePanel(ok) {
    const old = document.getElementById("demo-code-panel");
    if (old) old.remove();
    const box = document.createElement("div");
    box.id = "demo-code-panel";
    box.innerHTML = '<h4>本机机器码</h4>' +
      '<div class="code" id="dmc">' + (DEVICE_HASH ? codeOf(DEVICE_HASH) : "获取中…") + "</div>" +
      '<div class="hint">把这个码发给客服即可开通授权；开通后本页会自动生效（无需重装）。<br>' +
      "同一台电脑如需 app 与网页都能用，请把两端各自显示的机器码一并发送。</div>" +
      '<div class="st" id="dmc-st">' + (LICENSED ? "状态：已授权" : "状态：未授权（可先用体验模式）") + "</div>" +
      '<div class="row"><button class="primary" id="dmc-copy">复制机器码</button>' +
      '<button id="dmc-refresh">开通了吗？刷新状态</button>' +
      '<button id="dmc-link">本机已装 app？一键直连</button>' +
      '<button id="dmc-close">关闭</button></div>';
    document.body.appendChild(box);
    const copy = box.querySelector("#dmc-copy");
    copy.onclick = async () => {
      try { await navigator.clipboard.writeText(codeOf(DEVICE_HASH)); copy.textContent = "已复制"; }
      catch (e) { copy.textContent = "请手动选中复制"; }
      setTimeout(() => (copy.textContent = "复制机器码"), 1500);
    };
    box.querySelector("#dmc-close").onclick = () => box.remove();
    box.querySelector("#dmc-link").onclick = async () => {
      const st = box.querySelector("#dmc-st");
      if (st) st.textContent = "正在连接本机 app…（浏览器可能询问是否允许访问本地网络，请选允许）";
      const ok = await tryHandshake();
      if (LICENSED) { box.remove(); return; }
      if (st) st.textContent = ok
        ? "已连上本机 app，但这台机器尚未授权；请把上面的机器码发给客服"
        : "未检测到本机 app（需先打开桌面版），或浏览器拒绝了本地网络访问";
    };
    box.querySelector("#dmc-refresh").onclick = async () => {
      await heartbeat();
      const st = box.querySelector("#dmc-st");
      if (st) st.textContent = LICENSED ? "状态：已授权 ✓" : "状态：仍未授权，请确认已把机器码发给客服";
      if (LICENSED) box.remove();
    };
    if (!ok) {
      const el = box.querySelector("#dmc");
      if (el) el.textContent = "无法连接授权服务器";
    }
  }

  function tick() {
    const t = $("db-time");
    const remaining = TRIAL_SECONDS - usedSeconds();
    if (remaining <= 0) {
      if (!locked) forceLock();
      if (timer) { clearInterval(timer); timer = null; }
      return;
    }
    if (t) t.textContent = fmt(remaining * 1000);
  }

  function start() {
    endAt = loadEnd();
    locked = endAt <= Date.now() || usedSeconds() >= TRIAL_SECONDS;
    // 体验版全程不可导出（业主要求：首次 20 分钟也不可导出）
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
    // 授权：注册本机、定时心跳、机器码入口
    ensureDevice();
    setInterval(heartbeat, 60000);
    const codeBtn = document.getElementById("db-code-btn");
    if (codeBtn) codeBtn.onclick = async () => { const ok = await ensureDevice(); showCodePanel(ok); };
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
