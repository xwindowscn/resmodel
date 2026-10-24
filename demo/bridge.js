/* T-202610-010 · Pyodide 桥：把 app 的 res_web.Api 放进浏览器，
   对 app.js 冒充 pywebview 的 window.pywebview.api，前端零改动。 */
(function () {
  "use strict";

  const PYODIDE_URL = "https://cdn.jsdelivr.net/pyodide/v0.28.0/full/";
  const ENGINE = [
    "res_engine.py", "res_schema.py", "res_wacc.py", "res_wacc_data.py",
    "res_export.py", "res_license.py", "res_web.py",
  ];
  const I18N = ["ar", "es", "id", "ja", "kk", "km", "ky", "lo", "my", "ru", "tg", "th", "uz", "vi", "zh-TW"];

  const LS_PROFILES = "resmodel_profiles_v1";
  const LS_SESSION = "resmodel_session_v1";

  let py = null;
  let callPy = null;
  const splash = () => document.getElementById("py-splash");
  const splashMsg = (s) => { const el = splash(); if (el) el.querySelector(".py-msg").textContent = s; };

  /* ── 浏览器侧：记录与自动保存（localStorage） ── */
  function readProfiles() {
    try { return JSON.parse(localStorage.getItem(LS_PROFILES) || "[]"); } catch (e) { return []; }
  }
  function writeProfiles(list) {
    try { localStorage.setItem(LS_PROFILES, JSON.stringify(list)); } catch (e) {}
  }
  const profilesApi = {
    profiles: async () => ({
      ok: true,
      items: readProfiles().map((p) => ({ id: p.id, name: p.name, savedAt: p.savedAt })),
    }),
    save_profile: async (name, values) => {
      const list = readProfiles();
      const stamp = new Date().toLocaleString("zh-CN", { hour12: false });
      const hit = list.find((p) => p.name === name);
      if (hit) { hit.values = values; hit.savedAt = stamp; }
      else list.unshift({ id: "p_" + Date.now().toString(36), name, values, savedAt: stamp });
      writeProfiles(list);
      return { ok: true, id: (hit || list[0]).id };
    },
    load_profile: async (id) => {
      const hit = readProfiles().find((p) => p.id === id);
      return hit ? { ok: true, name: hit.name, values: hit.values } : { ok: false, error: "记录不存在" };
    },
    delete_profile: async (id) => {
      writeProfiles(readProfiles().filter((p) => p.id !== id));
      return { ok: true };
    },
    autosave: async (values) => {
      try { localStorage.setItem(LS_SESSION, JSON.stringify({ at: Date.now(), values })); } catch (e) {}
      return { ok: true };
    },
    last_session: async () => {
      try {
        const s = JSON.parse(localStorage.getItem(LS_SESSION) || "null");
        return s && s.values ? { ok: true, values: s.values } : { ok: false };
      } catch (e) { return { ok: false }; }
    },
  };

  /* ── 授权：P1/P2 阶段先不启用，P4 接 worker ── */
  const licenseApi = {
    license_status: async () => ({ ok: true, enabled: false, licensed: false, remaining: null, trial: null }),
    license_plans: async () => ({ ok: true, plans: [] }),
    license_buy: async () => ({ ok: false, error: "网页版请前往 resmodel.com 购买" }),
    license_poll: async () => ({ ok: false }),
    license_restore: async () => ({ ok: false, error: "P4 阶段接入" }),
    license_transfer: async () => ({ ok: false, error: "P4 阶段接入" }),
    quit: async () => ({ ok: true }),
  };

  function b64ToBlob(b64) {
    const bin = atob(b64);
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    return new Blob([buf], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  }

  async function bootPy() {
    splashMsg("正在载入计算引擎…");
    py = await loadPyodide({ indexURL: PYODIDE_URL });

    splashMsg("正在装配 numpy / ssl…");
    await py.loadPackage(["numpy", "ssl"]);

    splashMsg("正在装载模型文件…");
    py.FS.mkdir("/app");
    py.FS.mkdir("/app/web");
    py.FS.mkdir("/app/web/i18n");
    py.FS.writeFile("/app/web/build_stamp.txt", window.__BUILD_STAMP__ || "");
    const fetchText = async (url) => {
      const r = await fetch(url, { cache: "force-cache" });
      if (!r.ok) throw new Error(url + " → HTTP " + r.status);
      return await r.text();
    };
    for (const f of ENGINE) py.FS.writeFile("/app/" + f, await fetchText("py/" + f));
    for (const c of I18N) {
      try { py.FS.writeFile("/app/web/i18n/" + c + ".json", await fetchText("i18n/" + c + ".json")); } catch (e) {}
    }

    splashMsg("正在初始化模型…");
    py.runPython(`
import sys, os, json, base64, types
sys.path.insert(0, "/app")

# 浏览器环境：伪造 webview 模块，让 Api.export 的保存对话框返回固定路径
_wv = types.ModuleType("webview"); _wv.SAVE_DIALOG = 1; _wv.OPEN_DIALOG = 2
sys.modules["webview"] = _wv

import res_web as RW, res_license as L, res_wacc as W, res_export as X

class _Win:
    def create_file_dialog(self, *a, **k):
        return ["/tmp/export.xlsx"]
    def evaluate_js(self, *a, **k):
        return None

API = RW.Api(L.Client(enabled=False))
API.window = _Win()
try:
    API.live = W.live_data(force=False)
except Exception:
    API.live = None

def _call(name, args_json):
    try:
        args = json.loads(args_json)
        fn = getattr(API, name)
        r = fn(*args)
        return json.dumps({"ok": True, "v": r}, default=str, ensure_ascii=False)
    except Exception as e:
        import traceback; traceback.print_exc()
        return json.dumps({"ok": False, "e": type(e).__name__ + ": " + str(e)}, ensure_ascii=False)

def _export(lang, tables, langs):
    try:
        r = API.export(lang, tables, langs)
        if r.get("ok"):
            with open(r["path"], "rb") as f:
                r = dict(r); r["b64"] = base64.b64encode(f.read()).decode()
                r["name"] = os.path.basename(r["path"])
        return json.dumps({"ok": True, "v": r}, default=str)
    except Exception as e:
        import traceback; traceback.print_exc()
        return json.dumps({"ok": False, "e": type(e).__name__ + ": " + str(e)})
`);

    callPy = py.globals.get("_call");
    const _export = py.globals.get("_export");
    const call = (name, args) => {
      const out = JSON.parse(callPy(name, JSON.stringify(args || [])));
      if (!out.ok) throw new Error(out.e);
      return out.v;
    };

    const api = {};
    ["schema", "field_options", "preset", "defaults", "compute", "scenarios",
      "sensitivity", "term_sensitivity", "wacc_data", "fx_rate", "i18n"].forEach((m) => {
      api[m] = async (...args) => call(m, args);
    });
    api.export = async (lang, tables, langs) => {
      if (window.__EXPORT_BLOCKED__) return { ok: false, error: window.__EXPORT_BLOCKED_MSG__ || "体验版不可导出" };
      const out = JSON.parse(_export(lang, JSON.stringify(tables || null), JSON.stringify(langs || null)));
      if (!out.ok) throw new Error(out.e);
      const r = out.v;
      if (r.ok && r.b64) {
        const url = URL.createObjectURL(b64ToBlob(r.b64));
        const a = document.createElement("a");
        a.href = url; a.download = r.name || "RES_Financial_Model.xlsx";
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 4000);
        return { ok: true, path: r.name, lang: r.lang };
      }
      return r;
    };
    Object.assign(api, profilesApi, licenseApi);

    window.pywebview = { api };
    if (splash()) splash().remove();
    window.dispatchEvent(new Event("pywebviewready"));
  }

  window.addEventListener("DOMContentLoaded", () => {
    bootPy().catch((e) => {
      console.error(e);
      splashMsg("计算引擎载入失败：" + e.message + "（请检查网络后刷新）");
    });
  });
})();
