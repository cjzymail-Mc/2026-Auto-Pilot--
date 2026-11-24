# -*- coding: utf-8 -*-
"""Save a leave draft after source-bound UI verification; routing/push stays prohibited.

The leave save endpoint is not a static literal in the SPA bundles (verified
2026-11-20 --api-scan), so the adapter gates by namespace instead: exactly one
POST to oa.api.qiaodan.com /Leave* whose body carries this form's unique reason
and operator. The concrete path is recorded from the first real save response
and journaled via the standard SaveController registry.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from bpm.evection_save import local_minute
from bpm.plan import file_hash, plan_hash
from bpm.save import SaveController, SaveError

API_HOST = "oa.api.qiaodan.com"
FORM_PATH = "/oa/leave"
LEAVE_API_PATH = re.compile(r"/[Ll]eave(?:/[A-Za-z0-9_/.-]+)?")
QUERY_PATH = "/leave/query/20/1"
UUID_SHAPE = re.compile(r"[0-9a-fA-F-]{32,36}")
NUMBER_SHAPE = re.compile(r"[A-Za-z0-9-]{6,50}")


def load_request(path, task_id, facts, facts_sha256, run_dir):
    """The authorization must bind this task, its facts bytes and the prior
    verified readback of the same values."""
    auth = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if (set(auth) != {"task_id", "mode", "allow_submit", "statement", "facts_sha256",
                      "prior_attempt", "prior_readback_sha256", "start", "end"}
            or auth["task_id"] != task_id or auth["mode"] != "save_draft"
            or auth["allow_submit"] is not False or not auth["statement"].strip()
            or auth["facts_sha256"] != facts_sha256
            or not re.fullmatch(r"attempt_\d{3,}", auth["prior_attempt"])):
        raise SaveError("保存授权未绑定本次同一任务及事实")
    start, end = local_minute(auth["start"]), local_minute(auth["end"])
    if (start != auth["start"] or end != auth["end"] or end <= start
            or start != facts["start"] or end != facts["end"]):
        raise SaveError("保存授权起止时点与本次事实不一致")
    prior = run_dir / auth["prior_attempt"] / "evidence/leave_readback.json"
    reference = json.loads(prior.read_text(encoding="utf-8"))
    if (file_hash(prior) != auth["prior_readback_sha256"]
            or reference.get("leave_type") != facts["leave_type"]
            or reference.get("reason") != facts["reason"]
            or local_minute(reference["detail"]["startTime"]) != facts["start"]
            or local_minute(reference["detail"]["endTime"]) != facts["end"]
            or reference.get("status") != "编制中"
            or reference.get("save_button_disabled") is not False):
        raise SaveError("先前的整单回读与本次事实不一致")
    return auth


def save_payload_matches(body_text, facts, operator):
    """Content gate until the first real save reveals the exact schema."""
    return (isinstance(body_text, str) and facts["reason"] in body_text
            and operator in body_text)


def find_identity(value, depth=0):
    """Locate the uuid/full-number pair inside an unknown response shape."""
    if depth > 4:
        return None
    if isinstance(value, dict):
        uuid_value, number = value.get("id"), value.get("bizNumber")
        if (isinstance(uuid_value, str) and isinstance(number, str)
                and UUID_SHAPE.fullmatch(uuid_value) and NUMBER_SHAPE.fullmatch(number)):
            return {"uuid": uuid_value, "biz_number": number}
        for child in value.values():
            found = find_identity(child, depth + 1)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_identity(child, depth + 1)
            if found:
                return found
    return None


class LeaveSaveController(SaveController):
    def _config_hash(self):
        digest = hashlib.sha256()
        for name in ("leave.py", "leave_save.py", "save.py", "network_guard.py"):
            digest.update(bytes.fromhex(file_hash(Path(__file__).with_name(name))))
        return digest.hexdigest()

    def _preflight(self):
        plan = self.plan
        try:
            proof = {key: Path(value["path"]) for key, value in plan["sources"].items()
                     if file_hash(value["path"]) == value["sha256"]}
            facts = json.loads(proof["facts"].read_text(encoding="utf-8-sig"))
            auth = load_request(proof["request"], plan["task_id"], facts,
                                plan["sources"]["facts"]["sha256"], self.attempt.parent)
            if (facts == plan["facts"] and auth == plan["authorization"]
                    and plan["operator"] == self.expected_operator
                    and plan_hash(plan) == self.plan_hash
                    and self._config_hash() == self.config_sha256):
                return []
        except (OSError, ValueError, TypeError, KeyError, SaveError):
            pass
        return [{"code": "LEAVE_SAVE_BINDING_FAILED"}]

    def _verify(self, snapshot, phase="before_save"):
        facts = self.plan["facts"]
        detail = snapshot.get("detail") or {}
        differences = [key for key, value in (("leave_type", facts["leave_type"]),
                                              ("reason", facts["reason"]))
                       if snapshot.get(key) != value]
        try:
            times_ok = (local_minute(detail.get("startTime")) == facts["start"]
                        and local_minute(detail.get("endTime")) == facts["end"])
        except ValueError:
            times_ok = False
        if not times_ok:
            differences.append("detail")
        if (snapshot.get("operator") != self.plan["operator"]
                or snapshot.get("extras_empty") is not True):
            differences.append("identity_or_extras")
        info = snapshot.get("page", {})
        if info.get("is_new") is not (phase == "before_save") or info.get("status") != "编制中":
            differences.append("page")
        return {"ok": not differences, "differences": differences,
                "snapshot_hash": self._content(snapshot)}


class LeaveSaveAdapter:
    def __init__(self, probe, form, plan, principal):
        self.probe, self.form, self.plan = probe, form, plan
        self.page = probe.page
        self.principal = principal
        self.operator = plan["operator"]
        self.allowed = False
        self.used = False
        self.reply = None
        self.side = None
        self.saved_path = None

    def _is_module_post(self, url):
        return (url.scheme == "https" and url.netloc == API_HOST and not url.query
                and not url.fragment and LEAVE_API_PATH.fullmatch(url.path)
                and url.path.lower() != QUERY_PATH)

    def allow_request(self, request):
        url = urlsplit(request.url)
        if (not self.allowed or self.used or request.method != "POST"
                or request.frame != self.page.main_frame
                or not self._is_module_post(url)
                or not save_payload_matches(request.post_data, self.plan["facts"],
                                            self.operator)):
            return False
        self.used = True
        return True

    def capture_snapshot(self):
        self.probe.assert_new(self.form)
        self.probe.verify_identity(self.principal)
        return self.probe.snapshot(self.form, self.plan["operator"], is_new=True)

    def screenshot(self, name):
        self.probe.shot(self.side or self.page, name + ".png")
        return "evidence/" + name + ".png"

    def is_save_response(self, response):
        return (response.request.method == "POST"
                and self._is_module_post(urlsplit(response.url)))

    def exact_save_button(self):
        button = self.form.get_by_role("button", name="保存", exact=True)
        count = button.count()
        return {"text": "保存", "count": count, "enabled": count == 1 and button.is_enabled(),
                "visible": count == 1 and button.is_visible(),
                "dialogs": self.page.locator(".ui-dialog:visible,[role=alertdialog]:visible").count()}

    def click_exact_save(self):
        if not SaveController._button_valid(self.exact_save_button()):
            raise SaveError("保存按钮不再唯一可用")
        self.allowed = True
        try:
            with self.page.expect_response(self.is_save_response, timeout=25000) as reply:
                self.form.get_by_role("button", name="保存", exact=True).click(timeout=10000)
            self.reply = reply.value
            self.saved_path = urlsplit(self.reply.url).path
            self.probe.log_event(event="leave_save_post", path=self.saved_path,
                                 status=self.reply.status)
        finally:
            self.allowed = False

    def observe_saved(self):
        if not self.used or not self.reply.ok:
            return None
        try:
            body = self.reply.json()
        except Exception:
            return None
        self.probe.save("save_response_body.json",
                        json.dumps(body, ensure_ascii=False, indent=1)[:20000])
        identity = find_identity(body)
        if not identity:
            return None
        UUID(identity["uuid"])
        number = identity["biz_number"]
        self.page.wait_for_timeout(600)
        if self.probe.header_value(self.form, "单据编号") != number:
            return None
        identity["status"] = "编制中"
        # The leave list's filter schema is not modelled; uniqueness rests on
        # the fresh response UUID paired with the form header number.
        return {"identity": identity, "unique": True,
                "dialogs": self.exact_save_button()["dialogs"]}

    def inspect_uncertain(self):
        return None

    def reopen(self, identity):
        from bpm.browser_probe import HOST
        if not self.side:
            self.side = self.probe.ctx.new_page()
        self.side.goto(HOST + FORM_PATH + "?type=view&id=" + identity["uuid"],
                       wait_until="domcontentloaded", timeout=45000)
        form = self.side.locator("qd-leave-detail:visible")
        form.wait_for(timeout=30000)
        self.side.wait_for_timeout(600)
        query = parse_qs(urlsplit(self.side.url).query)
        if query.get("type") != ["view"] or query.get("id") != [identity["uuid"]]:
            raise SaveError("重开单据身份未验证")
        self.probe.verify_identity(self.principal, page=self.side)
        snapshot = self.probe.snapshot(form, self.plan["operator"],
                                       is_new=False, page=self.side)
        snapshot["page"]["uuid"] = identity["uuid"]
        return snapshot

    def close_verification_page(self):
        if self.side:
            self.side.close()
            self.page.bring_to_front()
