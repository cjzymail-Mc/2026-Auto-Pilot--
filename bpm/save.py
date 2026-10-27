"""One-click UI draft save with durable intent and read-only reconciliation.

The adapter is deliberately narrow: it cannot submit, confirm dialogs, call a
write API, or create a new form. Methods are synchronous. Persisted intent is
never retried, including after a process restart.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from bpm.verify import digest, verify_snapshot


class SaveError(RuntimeError):
    pass


class SaveBusy(SaveError):
    pass


def config_hash(document_type):
    from bpm.types import resolve_type
    try:
        return resolve_type(document_type).sha256
    except (OSError, ValueError):
        raise SaveError("Configuration evidence unavailable") from None


class SaveController:
    def __init__(self, plan, adapter, attempt_dir, expected_operator=None, base_dir=None,
                 journal_dir=None):
        self.plan = copy.deepcopy(plan)
        self.adapter = adapter
        self.attempt = Path(attempt_dir).resolve()
        self.attempt.mkdir(parents=True, exist_ok=True)
        self.base_dir = base_dir
        self.expected_operator = expected_operator
        from bpm.plan import plan_hash
        self.plan_hash = plan_hash(self.plan)
        self.config_sha256 = config_hash(self.plan.get("document_type"))
        self.task_id = self.plan.get("task_id")
        if not isinstance(self.task_id, str) or not self.task_id.strip():
            raise SaveError("task_id required")
        # Shared by attempts in one run. A caller resuming in another run must
        # retain journal_dir; this is a task registry, not an attempt-local flag.
        self.registry = Path(journal_dir or self.attempt.parent / "save_tasks").resolve()
        self.registry.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha256(self.task_id.encode("utf-8")).hexdigest()
        self.journal = self.registry / (name + ".json")
        self.lock = self.registry / (name + ".lock")
        self.state = None

    def _write_json(self, path, data):
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)

    def _artifact(self, name, data):
        self._write_json(self.attempt / name, data)

    def _transition(self, status, **extra):
        state = dict(self.state or {})
        state.update({"task_id": self.task_id, "plan_hash": self.plan_hash,
                      "config_sha256": self.config_sha256,
                      "status": status, "updated_at": datetime.now(timezone.utc).isoformat(),
                      "attempt_dir": str(self.attempt), **extra})
        self._write_json(self.journal, state)
        self.state = state
        event = {"event": status, "task_id": self.task_id, "plan_hash": self.plan_hash,
                 "config_sha256": self.config_sha256, "attempt": self.attempt.name,
                 "at": state["updated_at"], "save_journal": str(self.journal)}
        with (self.attempt.parent / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self._artifact("save_result.json", state)
        return state

    def _preflight(self):
        from bpm.plan import validate_plan, plan_hash
        try:
            issues = validate_plan(self.plan, expected_operator=self.expected_operator,
                                   verify_sources=True, base_dir=self.base_dir)
        except (ValueError, TypeError, OSError):
            issues = [{"code": "INVALID_PLAN"}]
        authorization = self.plan.get("authorization", {})
        if not isinstance(authorization, dict):
            authorization = {}
        if (authorization.get("mode") != "save_draft"
                or authorization.get("task_id") != self.task_id
                or authorization.get("allow_submit") is not False
                or not isinstance(authorization.get("statement"), str)
                or not authorization.get("statement", "").strip()):
            issues.append({"code": "NO_TASK_DRAFT_AUTHORIZATION"})
        if plan_hash(self.plan) != self.plan_hash:
            issues.append({"code": "PLAN_CHANGED"})
        if config_hash(self.plan.get("document_type")) != self.config_sha256:
            issues.append({"code": "CONFIG_CHANGED"})
        return issues

    @staticmethod
    def _button_valid(button):
        return (isinstance(button, dict) and button.get("text") == "保存"
                and type(button.get("count")) is int and button["count"] == 1
                and button.get("enabled") is True and button.get("visible") is True
                and button.get("kind", "button") == "button"
                and not button.get("dialogs"))

    @staticmethod
    def _content(snapshot):
        # Observation timestamps must change between independent reads; business
        # content and page identity must not change between screenshot and click.
        content = copy.deepcopy(snapshot)
        content.pop("observed_at", None)
        return digest(content)

    def _screenshot(self, name):
        relative = self.adapter.screenshot(name)
        if not isinstance(relative, str) or not relative:
            raise SaveError("screenshot artifact missing")
        path = (self.attempt / relative).resolve()
        if not path.is_relative_to(self.attempt) or not path.is_file() or path.stat().st_size == 0:
            raise SaveError("screenshot must exist beneath attempt directory")
        return relative

    def _reconcile(self, observation=None):
        """This branch is read-only; uncertainty can never lead back to click."""
        if observation is None:
            observation = self.adapter.inspect_uncertain()
        if not isinstance(observation, dict):
            return self._transition("SAVE_UNCERTAIN", reason="No unique saved identity observed")
        self._artifact("save_observation.json", observation)
        if observation.get("dialogs"):
            return self._transition("SAVE_UNCERTAIN", reason="Unknown dialog; no automatic confirmation")
        identity = observation.get("identity")
        if not isinstance(identity, dict) or not identity.get("uuid") or not identity.get("biz_number"):
            return self._transition("SAVE_UNCERTAIN", reason="Unique saved UUID/full number not established")
        if observation.get("unique") is not True:
            return self._transition("SAVE_UNCERTAIN", pending_identity=identity,
                                    reason="Read-only lookup has not proven identity unique")
        pending = (self.state or {}).get("pending_identity")
        if pending and (pending.get("uuid") != identity.get("uuid")
                        or pending.get("biz_number") != identity.get("biz_number")):
            return self._transition("SAVE_UNCERTAIN", reason="Conflicting saved identity")
        # Persist the identity before attempting navigation/readback. A timeout
        # on reopen must not discard the only known candidate identity.
        self._transition("SAVE_UNCERTAIN", pending_identity=identity, reason="Awaiting persisted readback")
        reopened = self.adapter.reopen(identity)
        self._artifact("save_reopened_snapshot.json", reopened)
        verification = verify_snapshot(self.plan, reopened, phase="after_save", base_dir=self.base_dir)
        self._artifact("save_reopened_verification.json", verification)
        page = reopened.get("page", {})
        if page.get("uuid") != identity.get("uuid") or page.get("biz_number") != identity.get("biz_number"):
            return self._transition("SAVE_UNCERTAIN", reason="Reopened identity differs")
        if identity.get("status") != "编制中" or page.get("status") != "编制中":
            return self._transition("SAVE_UNCERTAIN", reason="Unsubmitted status not established")
        if not verification["ok"]:
            return self._transition("SAVE_UNCERTAIN", reason="Persisted readback mismatch",
                                    verification=verification)
        screenshot = self._screenshot("draft_saved")
        if config_hash(self.plan.get("document_type")) != self.config_sha256:
            return self._transition("SAVE_UNCERTAIN", reason="Configuration changed during persisted readback")
        return self._transition("SUCCESS_DRAFT_SAVED", identity=identity,
                                pending_identity=identity, screenshot=screenshot,
                                verification=verification)

    def run(self):
        # OS advisory locks are released on process exit/crash, unlike an
        # O_EXCL sentinel, so a restarted process can reconcile saved intent.
        lock_stream = self.lock.open("a+b")
        try:
            if self.lock.stat().st_size == 0:
                lock_stream.write(b"0")
                lock_stream.flush()
            lock_stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock_stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            lock_stream.close()
            raise SaveBusy("Save task locked by another executor; wait for that executor to finish") from None
        try:
            if self.journal.exists():
                self.state = json.loads(self.journal.read_text(encoding="utf-8"))
                if self.state.get("task_id") != self.task_id or self.state.get("plan_hash") != self.plan_hash:
                    raise SaveError("Existing task journal binds a different plan; cannot overwrite or save")
                if self.state.get("config_sha256") != self.config_sha256 or config_hash(self.plan.get("document_type")) != self.config_sha256:
                    raise SaveError("Existing task journal binds a different configuration; read-only investigation required")
                status = self.state.get("status")
                if status not in {"NEEDS_INPUT", "READBACK_MISMATCH", "SAVE_INTENT", "SAVE_UNCERTAIN", "SUCCESS_DRAFT_SAVED"}:
                    raise SaveError("Unrecognized persisted save state; read-only investigation required")
                if status in ("SAVE_INTENT", "SAVE_UNCERTAIN", "SUCCESS_DRAFT_SAVED") or self.state.get("pending_identity") or self.state.get("identity"):
                    try:
                        identity = self.state.get("identity") or self.state.get("pending_identity")
                        if identity:
                            return self._reconcile({"identity": identity, "unique": True})
                        return self._reconcile()
                    except Exception as exc:
                        return self._transition("SAVE_UNCERTAIN", reason="Reconciliation failed: " + type(exc).__name__)
            issues = self._preflight()
            if issues:
                return self._transition("NEEDS_INPUT", issues=issues)
            try:
                first = self.adapter.capture_snapshot()
                self._artifact("save_before_snapshot.json", first)
                verification = verify_snapshot(self.plan, first, base_dir=self.base_dir)
                self._artifact("save_before_verification.json", verification)
                if not verification["ok"]:
                    return self._transition("READBACK_MISMATCH", verification=verification)
                screenshot = self._screenshot("before_save")
                second = self.adapter.capture_snapshot()
                self._artifact("save_click_snapshot.json", second)
                fresh = verify_snapshot(self.plan, second, base_dir=self.base_dir)
                if not fresh["ok"] or self._content(first) != self._content(second):
                    return self._transition("READBACK_MISMATCH", reason="Page changed after screenshot",
                                            verification=fresh)
                issues = self._preflight()
                if issues:
                    return self._transition("NEEDS_INPUT", issues=issues)
                button = self.adapter.exact_save_button()
                if not self._button_valid(button):
                    return self._transition("NEEDS_INPUT", reason="Unique exact 保存 button unavailable")
            except Exception as exc:
                return self._transition("NEEDS_INPUT", reason="Pre-save check failed: " + type(exc).__name__)
            self._transition("SAVE_INTENT", screenshot=screenshot,
                             pre_save_snapshot_hash=fresh["snapshot_hash"], button=button)
            try:
                if config_hash(self.plan.get("document_type")) != self.config_sha256:
                    return self._transition("SAVE_UNCERTAIN", reason="Configuration changed immediately before click")
                self.adapter.click_exact_save()
                observation = self.adapter.observe_saved()
                return self._reconcile(observation)
            except Exception as exc:
                return self._transition("SAVE_UNCERTAIN", reason="Save outcome unknown: " + type(exc).__name__)
        finally:
            lock_stream.close()
