"""Save a normal out-of-office draft after source-bound UI verification."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from bpm.plan import file_hash, plan_hash
from bpm.save import SaveController, SaveError


SAVE_PATH = "/evection/detail"
API_HOST = "oa.api.qiaodan.com"
CALC_POSTS = {
    ("ams.api.qiaodan.com", "/shiftapi/getleavereckon"),
    (API_HOST, "/evection/continuousdays"),
    (API_HOST, "/evection/connrestday"),
    (API_HOST, "/workout/getcardlistforworkout"),
}
LOCAL_TZ = timezone(timedelta(hours=8))


def local_minute(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::00(?:\.0+)?)?(?:Z|[+-]\d{2}:\d{2})?", value
    ):
        raise ValueError("unrecognized date and minute")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(LOCAL_TZ)
    return dt.strftime("%Y-%m-%dT%H:%M")


def load_request(path, task_id, trips, source_hash, run_dir):
    auth = json.loads(path.read_text(encoding="utf-8-sig"))
    if (set(auth) != {"task_id", "mode", "allow_submit", "statement", "start", "end",
                     "image_sha256", "prior_attempt", "prior_readback_sha256"}
            or auth["task_id"] != task_id or auth["mode"] != "save_draft"
            or auth["allow_submit"] is not False or not auth["statement"].strip()
            or auth["image_sha256"] != source_hash
            or not re.fullmatch(r"attempt_\d{3,}", auth["prior_attempt"])):
        raise SaveError("保存授权未绑定本次同一任务及图片")
    start, end = local_minute(auth["start"]), local_minute(auth["end"])
    if (start != auth["start"] or end != auth["end"] or end <= start
            or start[:10] != min(row[2] for row in trips)
            or end[:10] != max(row[3] for row in trips)):
        raise SaveError("出差明细日期或具体时分未核实")
    prior = run_dir / auth["prior_attempt"] / "evidence/trip_readback.json"
    reference = json.loads(prior.read_text(encoding="utf-8"))
    if (file_hash(prior) != auth["prior_readback_sha256"] or reference.get("trips") != trips
            or not reference.get("purpose")):
        raise SaveError("先前的整表回读已变化")
    return auth, reference["purpose"]


def zero(value):
    try:
        return value in (None, "") or Decimal(str(value)) == 0
    except InvalidOperation:
        return False


def draft_payload_matches(body, plan, cities):
    try:
        header, details, trips, costs = (body[key] for key in ("evection", "details", "trips", "costs"))
        if (set(body) != {"evection", "details", "trips", "costs"} or len(details) != 1
                or len(trips) != len(plan["trips"]) or len(costs) > 1
                or header.get("id") or header.get("bizNumber")
                or header.get("tripMode") == "plane" or header.get("isUseCar")
                or header.get("useCarRelationId") or header.get("useTickRelationId")
                or header.get("bizReason") != plan["purpose"]
                or header.get("appliedName") != plan["operator"]
                or header.get("createdName") != plan["operator"]
                or not zero(header.get("totalAmount"))):
            return False
        detail, = details
        if (detail.get("appliedName") != plan["operator"] or detail.get("id")
                or local_minute(detail["startTime"]) != plan["authorization"]["start"]
                or local_minute(detail["endTime"]) != plan["authorization"]["end"]):
            return False
        for actual, expected in zip(trips, plan["trips"]):
            values = [actual["startPlace"], actual["place"], local_minute(actual["startTime"])[:10],
                      local_minute(actual["endTime"])[:10], str(actual["days"]), actual["workItems"]]
            if (values != expected or actual.get("id")
                    or str(actual["startPlaceCode"]) != cities[expected[0]]
                    or str(actual["placeCode"]) != cities[expected[1]]):
                return False
        return all(all(value in (None, "") or (key in {"amount", "itemNumber"} and zero(value))
                       for key, value in cost.items()) for cost in costs)
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


class EvectionSaveController(SaveController):
    def _config_hash(self):
        h = hashlib.sha256()
        for name in ("evection.py", "evection_save.py", "save.py", "network_guard.py"):
            h.update(bytes.fromhex(file_hash(Path(__file__).with_name(name))))
        return h.hexdigest()

    def _preflight(self):
        plan = self.plan
        try:
            from bpm.evection import itinerary
            proof = {key: Path(value["path"]) for key, value in plan["sources"].items()
                     if file_hash(value["path"]) == value["sha256"]}
            source = itinerary(proof["image"], proof["itinerary"])
            auth, purpose = load_request(proof["request"], plan["task_id"], source["trips"],
                                         source["image_sha256"], self.attempt.parent)
            if (source["trips"] == plan["trips"] and auth == plan["authorization"]
                    and purpose == plan["purpose"] and plan["operator"] == self.expected_operator
                    and plan_hash(plan) == self.plan_hash and self._config_hash() == self.config_sha256):
                return []
        except (OSError, ValueError, TypeError, KeyError, SaveError):
            pass
        return [{"code": "EVECTION_SAVE_BINDING_FAILED"}]

    def _verify(self, snapshot, phase="before_save"):
        expected = {"trips": self.plan["trips"], "purpose": self.plan["purpose"],
                    "times": [self.plan["authorization"][key] for key in ("start", "end")],
                    "operator": self.plan["operator"], "details_count": 1, "extras_empty": True}
        differences = [key for key, value in expected.items() if snapshot.get(key) != value]
        info = snapshot.get("page", {})
        if info.get("is_new") is not (phase == "before_save") or info.get("status") != "编制中":
            differences.append("page")
        return {"ok": not differences, "differences": differences,
                "snapshot_hash": self._content(snapshot)}


class EvectionSaveAdapter:
    def __init__(self, probe, form, plan, principal, defaults):
        self.probe, self.form, self.plan = probe, form, plan
        self.page = probe.page
        self.principal, self.defaults = principal, defaults
        self.allowed = False
        self.used = False
        self.reply = None
        self.side = None

    def allow_request(self, request):
        url = urlsplit(request.url)
        if (not self.allowed or self.used or request.method != "POST" or request.frame != self.page.main_frame
                or url.scheme != "https" or url.netloc != API_HOST or url.path.lower() != SAVE_PATH
                or url.query or url.fragment):
            return False
        try:
            valid = draft_payload_matches(request.post_data_json, self.plan, self.probe.city_codes)
        except Exception:
            valid = False
        if valid:
            self.used = True
        return valid

    def capture_snapshot(self):
        self.probe.assert_new(self.form)
        self.probe.verify_identity(self.principal)
        return self.probe.draft_snapshot(self.form, self.defaults, self.principal["name"], is_new=True)

    def screenshot(self, name):
        self.probe.shot(self.side or self.page, name + ".png")
        return "evidence/" + name + ".png"

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
            with self.page.expect_response(lambda r: r.request.method == "POST"
                    and urlsplit(r.url).netloc == API_HOST and urlsplit(r.url).path.lower() == SAVE_PATH,
                    timeout=25000) as reply:
                self.form.get_by_role("button", name="保存", exact=True).click(timeout=10000)
            self.reply = reply.value
        finally:
            self.allowed = False

    def observe_saved(self):
        if not self.used or not self.reply.ok:
            return None
        value = self.reply.json()["evection"]
        uuid, number = value["id"], value["bizNumber"]
        UUID(uuid)
        if not re.fullmatch(r"[A-Za-z0-9-]{6,50}", number):
            return None
        self.page.wait_for_timeout(600)
        if self.probe.header_value(self.form, "单据编号") != number:
            return None
        identity = {"uuid": uuid, "biz_number": number, "status": "编制中"}
        # Record the response identity even if the subsequent lookup is blocked.
        if self.exact_save_button()["dialogs"]:
            return {"identity": identity, "unique": False, "dialogs": True}
        paired = self.exact_list_lookup(identity)
        return {"identity": identity, "unique": paired}

    def exact_list_lookup(self, identity):
        from bpm.evection import HOST, LIST, LIST_PATH, read_value, unique
        from bpm.template import parse_list_items
        self.side = self.probe.ctx.new_page()
        def is_list_reply(response):
            url = urlsplit(response.url)
            return (response.request.method == "POST" and url.scheme == "https"
                    and url.netloc == API_HOST and url.path.lower() == "/evection/query/20/1")
        with self.side.expect_response(is_list_reply, timeout=30000) as initial:
            self.side.goto(HOST + LIST_PATH, wait_until="domcontentloaded")
        if not initial.value.ok:
            return False
        listing = self.side.locator(f"{LIST}:visible")
        field = listing.locator("input#BizNumber0:visible")
        field.wait_for(timeout=30000)
        self.probe.verify_identity(self.principal, page=self.side)
        field.fill(identity["biz_number"])
        with self.side.expect_response(is_list_reply, timeout=20000) as query:
            self.probe.click_button(listing, "查询")
        if not query.value.ok:
            return False
        matches = [row for row in parse_list_items(query.value.text())
                   if row.get("bizNumber") == identity["biz_number"]]
        if len(matches) != 1 or matches[0].get("id") != identity["uuid"]:
            return False
        self.side.wait_for_timeout(600)
        row = listing.locator("tbody > tr:visible").filter(has=self.side.locator("td.prop-bizNumber").filter(
            has_text=re.compile(r"^\s*" + re.escape(identity["biz_number"]) + r"\s*$")))
        return read_value(unique(row.locator("td.prop-bizStatus"), "保存后列表状态")) == "编制中"

    def inspect_uncertain(self):
        return None

    def reopen(self, identity):
        from bpm.evection import HOST, FORM, FORM_PATH
        if not self.side:
            self.side = self.probe.ctx.new_page()
        self.side.goto(HOST + FORM_PATH + "?type=view&id=" + identity["uuid"], wait_until="domcontentloaded")
        form = self.side.locator(f"{FORM}:visible")
        form.get_by_text("行程安排", exact=True).wait_for(timeout=30000)
        self.side.wait_for_timeout(600)
        query = parse_qs(urlsplit(self.side.url).query)
        if query.get("type") != ["view"] or query.get("id") != [identity["uuid"]]:
            raise SaveError("重开单据身份未验证")
        self.probe.verify_identity(self.principal, page=self.side)
        snapshot = self.probe.draft_snapshot(form, self.defaults, self.principal["name"],
                                             is_new=False, page=self.side)
        snapshot["page"]["uuid"] = identity["uuid"]
        return snapshot

    def close_verification_page(self):
        if self.side:
            self.side.close()
            self.page.bring_to_front()
