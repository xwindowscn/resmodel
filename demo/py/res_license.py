#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RES Financial Model 授权客户端：设备指纹、token 校验、离线状态、联网心跳。"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser

BASE_URL = os.environ.get("RES_LICENSE_URL", "https://license.resmodel.com")
PUBLIC_KEY_HEX = "862618f220e73da33123c84b71d45c7a663959df90b96f448e2c2f16f1ce70a4"
SALT = "yellowfir-rne-2026"
OFFLINE_TRIAL_MAX = 1800
PAID_OFFLINE_GRACE = 72 * 3600
PLATFORM_NAME = ("Windows" if sys.platform.startswith("win")
                 else "macOS" if sys.platform == "darwin" else "Linux")
USER_AGENT = f"RESFinancialModel/3.1 ({PLATFORM_NAME})"

PLANS_FALLBACK = [
    {"id": "d1", "name_cn": "1 天", "name_en": "1 day", "days": 1, "price_cents": 200},
    {"id": "d7", "name_cn": "7 天", "name_en": "7 days", "days": 7, "price_cents": 500},
    {"id": "m1", "name_cn": "1 月", "name_en": "1 month", "days": 30, "price_cents": 700},
    {"id": "m3", "name_cn": "3 月", "name_en": "3 months", "days": 90, "price_cents": 1200},
    {"id": "m6", "name_cn": "半年", "name_en": "6 months", "days": 180, "price_cents": 2000},
    {"id": "y1", "name_cn": "一年", "name_en": "1 year", "days": 365, "price_cents": 3500},
    {"id": "life", "name_cn": "永久", "name_en": "Lifetime", "days": None, "price_cents": 5000},
]


def hash_device_uuid(uuid: str) -> str:
    return hashlib.sha256((SALT + uuid).encode()).hexdigest()


def _run_quiet(cmd):
    kw = {}
    if sys.platform.startswith("win"):
        kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5, **kw).stdout


def _read_platform_uuid() -> str:
    try:
        if sys.platform == "darwin":
            out = _run_quiet(["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"])
            m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
            return m.group(1) if m else ""
        if sys.platform.startswith("win"):
            out = _run_quiet([
                "reg", "query", r"HKLM\SOFTWARE\Microsoft\Cryptography",
                "/v", "MachineGuid"])
            m = re.search(r"MachineGuid\s+REG_SZ\s+([0-9a-fA-F-]+)", out)
            return m.group(1) if m else ""
        with open("/etc/machine-id", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _b64u_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_token(token: str, public_key_hex: str = PUBLIC_KEY_HEX) -> dict:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        payload_b64, sig_b64 = token.split(".")
        raw = _b64u_decode(payload_b64)
        sig = _b64u_decode(sig_b64)
    except Exception as exc:
        raise ValueError("malformed token") from exc
    key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
    try:
        key.verify(sig, raw)
    except InvalidSignature as exc:
        raise ValueError("bad signature") from exc
    return json.loads(raw.decode())


class Client:
    def __init__(self, enabled=False, app_version="", state_dir=None,
                 base_url=None, device_uuid=None, public_key_hex=None,
                 clock=time.monotonic, wall_clock=time.time):
        self.enabled = bool(enabled)
        self.app_version = app_version
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.public_key_hex = public_key_hex or PUBLIC_KEY_HEX
        self._clock = clock
        self._wall = wall_clock
        self._uuid = device_uuid
        self._hash = None
        self._lock = threading.RLock()
        self._payload = None
        self._token = None
        self._token_mono = None
        self._last_ok_mono = None
        self._last_heartbeat = None
        self._stop = threading.Event()
        self._thread = None

        if not state_dir:
            if sys.platform.startswith("win"):
                root = os.environ.get("APPDATA") or os.path.expanduser("~")
            elif sys.platform == "darwin":
                root = os.path.join(os.path.expanduser("~"),
                                    "Library", "Application Support")
            else:
                root = os.environ.get("XDG_DATA_HOME") or os.path.join(
                    os.path.expanduser("~"), ".local", "share")
            state_dir = os.path.join(root, "RES Financial Model")
        base = state_dir
        self.state_dir = base
        self.state_path = os.path.join(base, "license_state.json")
        self._load()

    # ── 设备与持久化 ─────────────────────────────────────────────
    def device_hash(self) -> str:
        if self._hash:
            return self._hash
        if not self._uuid:
            self._uuid = _read_platform_uuid()
        if not self._uuid:
            try:
                host = os.uname().nodename
            except AttributeError:
                host = os.environ.get("COMPUTERNAME") or "host"
            self._uuid = "unknown-" + host
        self._hash = hash_device_uuid(self._uuid)
        return self._hash

    def _load(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return
        token = data.get("token")
        if not token:
            return
        try:
            payload = verify_token(token, self.public_key_hex)
        except ValueError:
            return
        if payload.get("device_hash") != self.device_hash():
            return
        self._apply_token(token)

    def _save(self, token: str):
        try:
            os.makedirs(self.state_dir, exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({"token": token, "device_hash": self.device_hash()}, f)
            os.replace(tmp, self.state_path)
        except OSError:
            pass

    # ── token 与状态 ─────────────────────────────────────────────
    def _apply_token(self, token: str):
        payload = verify_token(token, self.public_key_hex)
        if payload.get("device_hash") != self.device_hash():
            raise ValueError("token for another device")
        with self._lock:
            self._payload = payload
            self._token = token
            self._token_mono = self._clock()
            self._last_ok_mono = self._clock()
        self._save(token)

    def _effective_now(self, payload):
        return float(payload.get("server_now", 0)) + (self._clock() - self._token_mono)

    def status(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "licensed": True, "gated": False,
                    "mode": "unlimited", "remaining_seconds": None,
                    "offline": False, "message": ""}
        with self._lock:
            payload = self._payload
            token_mono = self._token_mono
            last_ok = self._last_ok_mono
        if payload is None:
            return {"enabled": True, "licensed": False, "gated": True,
                    "mode": "unknown", "remaining_seconds": 0,
                    "offline": True, "message": "需要联网验证授权"}

        now_eff = self._effective_now(payload)
        lic = payload.get("license")
        licensed = bool(
            lic and lic.get("status") == "active"
            and (lic.get("expires_at") is None or lic["expires_at"] > now_eff))
        offline_for = self._clock() - (last_ok if last_ok is not None else token_mono)

        if licensed:
            remaining = (None if lic["expires_at"] is None
                         else int(max(0, lic["expires_at"] - now_eff)))
            gated = offline_for > PAID_OFFLINE_GRACE
            mode = "lifetime" if lic["expires_at"] is None else "paid"
            msg = "离线超过 72 小时，请联网验证" if gated else ""
        else:
            trial_remaining = int(max(0, payload.get("trial_remaining", 0)
                                      - (self._clock() - token_mono)))
            gated = trial_remaining <= 0 or offline_for > OFFLINE_TRIAL_MAX
            remaining = trial_remaining
            mode = "expired" if gated else "trial"
            msg = ""
            if offline_for > OFFLINE_TRIAL_MAX:
                msg = "离线试用已达 30 分钟，请联网"
            elif gated:
                msg = "试用已结束"

        return {"enabled": True, "licensed": licensed, "gated": gated,
                "mode": mode, "remaining_seconds": remaining,
                "offline": offline_for > 300, "message": msg,
                "license": lic}

    # ── HTTP ───────────────────────────────────────────────────
    def _post(self, path, body, timeout=8):
        req = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(body).encode(),
            headers={"content-type": "application/json",
                     "accept": "application/json",
                     "user-agent": USER_AGENT},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            try:
                return json.loads(exc.read().decode())
            except Exception:
                return {"ok": False, "error": f"HTTP {exc.code}"}
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def _get(self, path, timeout=8):
        try:
            req = urllib.request.Request(
                self.base_url + path,
                headers={"accept": "application/json", "user-agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def _take_token(self, res) -> dict:
        if not res.get("ok") or not res.get("token"):
            return res
        try:
            self._apply_token(res["token"])
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return res

    def register(self) -> dict:
        res = self._take_token(self._post("/v1/register", {
            "device_hash": self.device_hash(),
            "app_version": self.app_version,
            "os": PLATFORM_NAME,
        }))
        if res.get("ok"):
            with self._lock:
                self._last_heartbeat = self._clock()
        return res

    def heartbeat(self) -> dict:
        with self._lock:
            last = self._last_heartbeat
        if last is None:
            last = self._clock()
        elapsed = int(max(0.0, self._clock() - last) * 1000)
        res = self._take_token(self._post("/v1/heartbeat", {
            "device_hash": self.device_hash(),
            "elapsed_ms": elapsed,
            "app_version": self.app_version,
        }))
        if res.get("ok"):
            with self._lock:
                self._last_heartbeat = self._clock()
        return res

    # ── 购买与恢复 ─────────────────────────────────────────────
    def _refresh(self) -> dict:
        return self.register()

    def plans(self) -> list:
        res = self._get("/v1/plans")
        if res.get("ok") and isinstance(res.get("plans"), list):
            return res["plans"]
        return PLANS_FALLBACK

    def buy(self, plan_id: str) -> dict:
        if not self.enabled:
            return {"ok": False, "error": "license_disabled"}
        res = self._post("/v1/order", {
            "device_hash": self.device_hash(),
            "plan_id": plan_id,
        })
        if not res.get("ok"):
            return res
        url = res.get("checkout_url")
        if url:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return {"ok": True, "order_id": res["order_id"], "checkout_url": url}

    def poll(self, order_id: str) -> dict:
        res = self._get(f"/v1/order/{order_id}")
        if res.get("ok") and res.get("status") == "paid":
            if res.get("token"):
                self._take_token(res)
            else:
                self._refresh()
            res["license"] = self.status()
        return res

    def transfer(self, order_id: str) -> dict:
        res = self._post("/v1/transfer", {
            "device_hash": self.device_hash(),
            "order_id": order_id,
        })
        if res.get("ok"):
            self._take_token(res)
            res["license"] = self.status()
        return res

    def restore(self, order_id: str) -> dict:
        res = self._post("/v1/restore", {
            "device_hash": self.device_hash(),
            "order_id": order_id,
        })
        if res.get("ok"):
            self._take_token(res)
            res["license"] = self.status()
        return res

    # ── 后台线程 ───────────────────────────────────────────────
    def start(self):
        if not self.enabled or self._thread is not None:
            return
        with self._lock:
            self._last_heartbeat = self._clock()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        self.register()
        while not self._stop.wait(60):
            self.heartbeat()

    def stop(self):
        self._stop.set()
