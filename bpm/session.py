"""Local login metadata; credentials remain exclusively in the protected profile."""
from __future__ import annotations

import base64
import json
import math
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from bpm.paths import ROOT
ORIGIN = "https://bpm.qiaodan.com"
LOCAL_ROOT = ROOT / "automation/.local-session"
REUSE_DAYS = 30
# 60 天时期写入的合法旧记录不整体作废：days 仍可读到 60，但生效窗口收紧到
# min(原窗口, last_scan_at+30 天)——未满 30 天不拒、恰满/超过失效、更短旧窗口不延长。
LEGACY_MAX_DAYS = 60
LEGACY_TTL = 24 * 3600
META_KEY = "_bpm_login_metadata"


def iso(epoch):
    if not isinstance(epoch, (int, float)) or isinstance(epoch, bool) or not math.isfinite(epoch):
        return None
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def claims(token):
    """Read expiry/identity hints only; never treat decoding as authentication."""
    if not isinstance(token, str) or len(token) > 100000 or token.count(".") != 2:
        return {}
    try:
        part = token.split(".")[1]
        value = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        return value if isinstance(value, dict) else {}
    except (ValueError, TypeError, UnicodeError):
        return {}


def token_metadata(state):
    local = {}
    for origin in state.get("origins", []):
        if origin.get("origin") == ORIGIN:
            local.update({entry["name"]: entry.get("value") for entry in origin.get("localStorage", [])})
    session = state.get("_page_storage", {}).get(ORIGIN, {})
    result = {}
    for kind in ("access", "refresh"):
        key = "qd_" + kind + "_token"
        data = claims(session.get(key) or local.get(key))
        expiry = data.get("exp")
        result[kind + "_expires_epoch"] = (expiry if isinstance(expiry, (int, float))
            and not isinstance(expiry, bool) and math.isfinite(expiry) and expiry > 0 else None)
        result[kind + "_subject"] = str(data["sub"]) if data.get("sub") is not None else None
        result[kind + "_claims"] = data
    return result


def read_state(path):
    try:
        data = Path(path).read_text(encoding="utf-8")
        value = json.loads(data)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def _meta_valid(meta):
    """meta 完整性统一口径：读取判定 / 非 scan 复制 / 写回展示三处同一拒绝。

    缺 profile_id/session_generation、坏 schema/起点/天数、显式 null 一律不通过——
    不允许"读取放行、写回才拒"或"损坏被当合法无元数据旧状态"。
    """
    if not isinstance(meta, dict) or meta.get("schema_version") != "1.0":
        return False
    start = meta.get("last_scan_epoch")
    days = meta.get("local_reuse_days")
    if (isinstance(start, bool) or not isinstance(start, (int, float))
            or not math.isfinite(start) or not isinstance(days, int) or isinstance(days, bool)
            or not 1 <= days <= LEGACY_MAX_DAYS):
        return False
    for key in ("profile_id", "session_generation"):
        value = meta.get(key)
        if (not isinstance(value, str) or len(value) != 32
                or any(char not in "0123456789abcdef" for char in value)):
            return False
    return True


def state_usable(path, now=None, ttl=REUSE_DAYS * 86400):
    """A local reuse decision, always followed by live login/identity verification."""
    now = time.time() if now is None else now
    try:
        path = Path(path)
        if path.stat().st_size <= 0:
            return False
        state = read_state(path)
        if not state and path.read_text(encoding="utf-8").strip() != "{}":
            return False
        if META_KEY not in state:
            # 真旧文件（从未写过 meta 键）才按 mtime+24h；显式 null/损坏 meta 一律
            # 拒绝，不把"存在但损坏"伪装成"合法无元数据旧状态"。
            return 0 <= now - path.stat().st_mtime < min(ttl, LEGACY_TTL)
        if not _meta_valid(state[META_KEY]):
            return False
        start = state[META_KEY]["last_scan_epoch"]
        days = state[META_KEY]["local_reuse_days"]
        if not 0 <= now - start < min(ttl, days * 86400, REUSE_DAYS * 86400):
            return False
        tokens = token_metadata(state)
        if (tokens["access_subject"] and tokens["refresh_subject"]
                and tokens["access_subject"] != tokens["refresh_subject"]):
            return False
        refresh_expiry = tokens["refresh_expires_epoch"]
        return refresh_expiry is None or now < refresh_expiry
    except (OSError, ValueError, TypeError, OverflowError, AttributeError):
        return False


def attach_metadata(state, previous, *, fresh_scan=False, now=None):
    now = time.time() if now is None else now
    current_tokens = token_metadata(state)
    old_tokens = token_metadata(previous)
    old = previous.get(META_KEY, {})
    subject = current_tokens["refresh_subject"] or current_tokens["access_subject"]
    old_subject = old_tokens["refresh_subject"] or old_tokens["access_subject"]
    if (current_tokens["access_subject"] and current_tokens["refresh_subject"]
            and current_tokens["access_subject"] != current_tokens["refresh_subject"]):
        raise ValueError("Access and refresh identity mismatch")
    if fresh_scan:
        meta = {"schema_version": "1.0", "profile_id": uuid.uuid4().hex,
                "session_generation": uuid.uuid4().hex, "last_scan_epoch": now,
                "local_reuse_days": REUSE_DAYS}
    elif _meta_valid(old) and subject and subject == old_subject:
        # 只复制通过统一校验的旧 meta；坏 schema/缺标识不复制（返回 None 保守处理）。
        meta = dict(old)
    else:
        # No observed fresh scan: keep legacy expiry rather than invent a scan.
        return None
    meta["last_authenticated_epoch"] = now
    state[META_KEY] = meta
    return meta


def observed_identity(page, state):
    account = page.locator("a#user-profile-dd.profile-toggle-link > span")
    if account.count() != 1 or not account.is_visible():
        raise ValueError("Authenticated account header not unique")
    name = account.inner_text().strip()
    if not name:
        raise ValueError("Authenticated account name missing")
    data = token_metadata(state)
    access = data["access_claims"]
    refresh = data["refresh_claims"]
    for payload in (access, refresh):
        if payload.get("full_name") and str(payload["full_name"]).strip() != name:
            raise ValueError("Account header and token identity differ")
    return {"user_id": data["access_subject"] or data["refresh_subject"],
            "employee_id": access.get("employee_id") or refresh.get("employee_id"),
            "name": name, "company": None, "department": None}


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def persist_state(path, state, previous):
    """普通探查写回：无可信扫码 meta 的真旧文件保留原 mtime（24h 锚点不滑动）。

    previous 为写回前的 read_state 结果。attach_metadata 未产出 meta 且旧文件本就
    没有 meta 时，os.replace 后恢复原 mtime——凭证值照常刷新，但 24h 边界不因写回
    滚动续期；不补扫码时间、不授予新窗口。
    """
    path = Path(path)
    previous = previous if isinstance(previous, dict) else {}
    if META_KEY in previous and not _meta_valid(previous[META_KEY]) and META_KEY not in state:
        # 旧 meta 存在但无效（坏 schema/缺标识/显式 null）且本次非扫码未产出新 meta：
        # 覆盖会把"坏元数据"降级成"无元数据"绕回 legacy 24h——覆盖前拒绝并保持原字节，
        # 真实新扫码（attach 产出新 meta）仍正常重建。
        raise ValueError("Corrupt prior login metadata; fresh scan required to rebuild")
    previous_mtime = path.stat().st_mtime if path.exists() else None
    previous_had_meta = isinstance(previous.get(META_KEY), dict) and previous.get(META_KEY)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    if previous_mtime is not None and not previous_had_meta and META_KEY not in state:
        os.utime(path, (time.time(), previous_mtime))


def write_record(state, principal, *, root=LOCAL_ROOT, now=None):
    now = time.time() if now is None else now
    if META_KEY not in state:
        # 无扫码锚点（真旧状态）：不产会话记录——不编造 profile_id/扫码时间等字段。
        return None
    meta = state[META_KEY]
    if not _meta_valid(meta):
        raise ValueError("Invalid or incomplete local login metadata")
    profile_id = meta["profile_id"]
    start = meta["last_scan_epoch"]
    # 显示口径与读取判定一致：旧 60 天记录同样按 min(原窗口, 30 天) 显示期限。
    local_until = start + min(meta["local_reuse_days"], REUSE_DAYS) * 86400
    tokens = token_metadata(state)
    refresh_until = tokens["refresh_expires_epoch"]
    record = {"schema_version": "1.0", "profile_id": profile_id, "origin": ORIGIN,
              "session_generation": meta["session_generation"], "principal": principal,
              "default_creator": None, "default_applicant": None,
              "identity_source": "live_authenticated_account_header_and_token_subject",
              "identity_verification_level": "header_and_subject" if principal.get("user_id") else "header_only",
              "identity_checked_at": iso(now), "last_scan_at": iso(start),
              "last_authenticated_at": iso(now), "last_checked_at": iso(now),
              "auth_status": "authenticated", "local_reuse_days": meta["local_reuse_days"],
              "local_reuse_until": iso(local_until), "server_expires_at": None,
              "expiry_source": "JWT expiry metadata; server maximum unknown; live checks required",
              "access_token_expires_at": iso(tokens["access_expires_epoch"]),
              "relevant_credential_expires_at": iso(refresh_until),
              "effective_reuse_until": iso(min(local_until, refresh_until)) if refresh_until else iso(local_until),
              "credential_ref": "automation/.pw-profile/session_state.json",
              "last_check_reason": "Actual account header verified; company/department and form defaults not observed"}
    path = Path(root) / profile_id / "session_record.json"
    atomic_json(path, record)
    atomic_json(Path(root) / "current.json", {"schema_version": "1.0", "profile_id": profile_id,
                                               "record": profile_id + "/session_record.json"})
    return path
