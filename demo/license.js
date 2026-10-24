/* 授权：剩余时间 chip、收费墙、购买与恢复 */
"use strict";

const LicenseUI = (() => {
  const $ = (id) => document.getElementById(id);
  let orderId = null;
  let pollTimer = null;
  let statusTimer = null;
  let plansLoaded = false;
  let manualOpen = false;

  function money(cents) {
    return "$" + (cents / 100).toFixed(cents % 100 === 0 ? 0 : 2);
  }

  function fmtRemaining(sec) {
    if (sec === null || sec === undefined) return "永久";
    const d = Math.floor(sec / 86400);
    const h = Math.floor((sec % 86400) / 3600);
    const m = Math.ceil((sec % 3600) / 60);
    if (d > 0) return `${d} 天 ${h} 小时`;
    if (h > 0) return `${h} 小时 ${m} 分`;
    return `${m} 分钟`;
  }

  function renderChip(st) {
    const chip = $("license-chip");
    const text = $("license-chip-text");
    if (!chip) return;
    if (!st || st.enabled === false) {
      // general 版：无授权机制 → 显示「永久授权」
      chip.hidden = false;
      chip.classList.add("paid");
      chip.classList.remove("warn");
      chip.title = "";
      text.textContent = "永久授权";
      return;
    }
    chip.hidden = false;
    chip.classList.toggle("paid", st.mode === "paid" || st.mode === "lifetime");
    chip.classList.toggle("warn", st.mode === "trial" && (st.remaining_seconds || 0) <= 600);
    if (st.mode === "lifetime") text.textContent = "永久授权";
    else if (st.mode === "paid") text.textContent = `已购 · 剩余 ${fmtRemaining(st.remaining_seconds)}`;
    else if (st.mode === "trial") text.textContent = `试用剩余 ${fmtRemaining(st.remaining_seconds)}`;
    else if (st.mode === "unknown") text.textContent = "授权验证中";
    else text.textContent = "需要购买";
    chip.title = st.offline ? "离线状态" : "";
  }

  function showGate(st) {
    const gate = $("license-gate");
    if (!gate) return;
    const trial = !!(st && st.mode === "trial");
    const licensed = !!(st && st.licensed);
    const title = $("license-title");
    const titleEn = $("license-title-en");
    const later = $("license-later");
    if (title) title.textContent = trial ? "升级为正式版" : licensed ? "授权状态" : "使用时间已用完";
    if (titleEn) titleEn.textContent = trial ? "Upgrade to the full version" : licensed ? "License status" : "Trial ended";
    if (later) later.classList.toggle("hidden", !trial);
    const dev = $("license-device");
    const devVal = $("license-device-value");
    if (dev && devVal) {
      const hash = (st && (st.machine_code || st.device_hash)) || "";
      dev.hidden = !hash;
      if (hash) devVal.textContent = hash;
    }
    const ordLine = $("license-order-line");
    const ordVal = $("license-order-value");
    if (ordLine && ordVal) {
      const oid = st && st.order_id;
      ordLine.hidden = !oid;
      if (oid) ordVal.textContent = oid;
    }
    gate.classList.remove("hidden");
    $("license-reason").textContent = trial
      ? `试用期内可随时购买，付款后立即转为正式授权，无需等到试用结束。（试用剩余 ${fmtRemaining(st.remaining_seconds)}）`
      : licensed
        ? (st.mode === "lifetime" ? "永久授权有效。" : `授权有效，剩余 ${fmtRemaining(st.remaining_seconds)}。`)
        : (st && st.message ? st.message : "试用已结束。购买后可继续使用全部功能。");
    loadPlans();
  }

  function hideGate() {
    const gate = $("license-gate");
    if (gate) gate.classList.add("hidden");
  }

  async function loadPlans() {
    if (plansLoaded) return;
    plansLoaded = true;
    const box = $("license-plans");
    try {
      const res = await window.pywebview.api.license_plans();
      const plans = (res && res.plans) || [];
      box.innerHTML = plans.map((p) => `
        <button class="license-plan" data-plan="${p.id}">
          <span class="lp-name">${p.name_cn}<span class="en">${p.name_en || ""}</span></span>
          <span class="lp-price">${money(p.price_cents)}</span>
        </button>`).join("");
      box.querySelectorAll(".license-plan").forEach((b) => {
        b.addEventListener("click", () => buy(b.dataset.plan, b));
      });
    } catch (e) {
      box.innerHTML = `<p class="license-note">无法加载方案：${e}</p>`;
    }
  }

  function friendlyBuyError(err) {
    const s = String(err || "");
    if (s.includes("transaction_checkout_not_enabled")) {
      return "支付服务正在开通中，请稍后再试。Payment service is being activated — please try again later.";
    }
    if (s.includes("paddle_create_failed")) {
      return "支付服务暂时不可用，请稍后再试。Payment service is temporarily unavailable — please try again later.";
    }
    return s || "未知错误";
  }

  async function buy(planId, btn) {
    btn.disabled = true;
    try {
      const res = await window.pywebview.api.license_buy(planId);
      if (!res.ok) {
        setNote("下单失败：" + friendlyBuyError(res.error));
        btn.disabled = false;
        return;
      }
      orderId = res.order_id;
      setNote("已打开浏览器支付。完成后回到本窗口，状态会自动更新。");
      startPolling();
    } catch (e) {
      setNote("下单失败：" + friendlyBuyError(e));
      btn.disabled = false;
    }
  }

  function startPolling() {
    stopPolling();
    let tries = 0;
    pollTimer = setInterval(async () => {
      tries += 1;
      if (tries > 200) { stopPolling(); return; }
      await refreshOnce(true);
    }, 3000);
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  async function refreshOnce(fromPoll) {
    try {
      if (orderId && fromPoll) {
        const res = await window.pywebview.api.license_poll(orderId);
        if (res && res.ok && res.status === "paid" && res.license && res.license.licensed) {
          orderId = null;
          manualOpen = false;
          apply(res.license);
          hideGate();
          stopPolling();
          if (window.__rneCompute) window.__rneCompute();
          return;
        }
      }
      const st = await window.pywebview.api.license_status();
      apply(st);
    } catch (e) { /* 离线时静默 */ }
  }

  function apply(st) {
    if (!st) return;
    renderChip(st);
    if (st.gated) { showGate(st); return; }
    // 试用期内用户主动打开的购买面板保持打开，不因定时刷新被关闭
    if (manualOpen) {
      if (st.licensed) {
        manualOpen = false;
        orderId = null;
        hideGate();
        stopPolling();
        return;
      }
      if (st.mode === "trial" && !orderId) {
        setNote(`试用剩余 ${fmtRemaining(st.remaining_seconds)}，可随时购买；付款后立即解锁。`);
      }
      return;
    }
    hideGate();
  }

  function setNote(msg) {
    const el = $("license-note");
    if (el) el.textContent = msg;
  }

  const TRANSFER_ERRORS = {
    order_not_found: "订单号不存在或尚未付款。",
    not_found: "订单号不存在或尚未付款。",
    bad_order: "订单号格式不正确。",
    bad_device: "设备号无效，请重启软件后再试。",
    no_license: "该订单没有有效授权。",
    license_inactive: "该授权已停用（可能已退款）。",
    target_licensed: "本机已有有效授权，无需迁移。",
    transfer_cooldown: "迁移过于频繁，请 7 天后再试；如需紧急处理请联系客服。",
    transfer_limit: "该授权的自助迁移次数已用完，请联系客服。",
    conflict: "迁移冲突，请稍后重试。",
  };

  function unlockNote(license, msg) {
    orderId = null;
    manualOpen = false;
    apply(license);
    hideGate();
    stopPolling();
    if (window.__rneCompute) window.__rneCompute();
    setNote(msg);
  }

  function bind() {
    $("license-refresh").addEventListener("click", async () => {
      setNote("正在刷新…");
      await refreshOnce(true);
      setNote("若已完成支付仍显示未解锁，请稍后再试或使用订单号恢复。");
    });
    $("license-restore-btn").addEventListener("click", async () => {
      const order = ($("license-order").value || "").trim();
      if (!order) return setNote("请输入订单号。");
      const res = await window.pywebview.api.license_restore(order);
      if (res && res.ok && res.license && res.license.licensed) {
        unlockNote(res.license, "恢复成功。");
      } else {
        setNote("未找到可恢复的订单：" + ((res && res.error) || ""));
      }
    });
    $("license-transfer-btn").addEventListener("click", async () => {
      const order = ($("license-transfer-order").value || "").trim();
      if (!order) return setNote("请输入原电脑上的订单号。");
      setNote("正在迁移授权…");
      const res = await window.pywebview.api.license_transfer(order);
      if (res && res.ok && res.license && res.license.licensed) {
        unlockNote(res.license, "迁移成功，授权已转到本机。");
      } else {
        setNote(TRANSFER_ERRORS[(res && res.error) || ""] || "迁移失败：" + ((res && res.error) || ""));
      }
    });
    $("license-quit").addEventListener("click", () => {
      window.pywebview.api.quit();
    });
    $("license-later").addEventListener("click", () => {
      manualOpen = false;
      hideGate();
      if (!orderId) stopPolling();
    });
    const copyField = (valueId, label) => async () => {
      const el = $(valueId);
      const text = el ? el.textContent : "";
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        setNote(label + "已复制。");
      } catch (e) {
        const range = document.createRange();
        range.selectNodeContents(el);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
        try { document.execCommand("copy"); setNote(label + "已复制。"); }
        catch (_) { setNote("请手动选中" + label + "复制。"); }
      }
    };
    $("license-device-copy").addEventListener("click", copyField("license-device-value", "机器码"));
    $("license-order-copy").addEventListener("click", copyField("license-order-value", "订单号"));
    $("license-chip").addEventListener("click", async () => {
      const st = await window.pywebview.api.license_status();
      if (st.gated) { apply(st); return; }
      manualOpen = true;
      showGate(st);
      if (st.mode === "trial" && !orderId) {
        setNote(`试用剩余 ${fmtRemaining(st.remaining_seconds)}，可随时购买；付款后立即解锁。`);
      }
    });
  }

  async function init() {
    bind();
    const st = await window.pywebview.api.license_status();
    apply(st);
    statusTimer = setInterval(() => refreshOnce(false), 30000);
    if (st.mode === "unknown") {
      let n = 0;
      const t = setInterval(async () => {
        n += 1;
        const s = await window.pywebview.api.license_status();
        apply(s);
        if (s.mode !== "unknown" || n > 20) clearInterval(t);
      }, 1000);
    }
  }

  return { init, apply, showGate, hideGate, refreshOnce };
})();
