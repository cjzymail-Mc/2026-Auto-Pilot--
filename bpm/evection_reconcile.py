"""Read-only recovery for an exact evection save response with an uncertain outcome."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from bpm.evection import EvectionProbe, save_json
from bpm.evection_save import EvectionSaveAdapter, EvectionSaveController
from bpm.paths import ROOT
from bpm.session import state_usable
from bpm.browser_probe import SESSION_STATE


def read_json(path):
    return path.read_text(encoding="utf-8")


def evidence_defaults(path):
    labels = ("申请人", "申请部门", "公司", "成本中心", "制单人", "制单部门")
    fields = json.loads(read_json(path))["layout"]["headers"]
    defaults = {}
    for label in labels:
        (field,) = [field for field in fields if field["text"] == label]
        (control,) = field["controls"]
        if not control["value"]:
            raise ValueError("prior default field missing")
        defaults[label] = control["value"]
    return defaults


class ReadOnlyAdapter(EvectionSaveAdapter):
    def __init__(self, probe, plan, principal, defaults, candidate):
        super().__init__(probe, None, plan, principal, defaults)
        self.candidate = candidate

    def inspect_uncertain(self):
        return {"identity": self.candidate, "unique": self.exact_list_lookup(self.candidate)}

    def click_exact_save(self):
        raise RuntimeError("read-only reconciliation cannot click Save")


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--run", required=True)
    cli.add_argument("--save-attempt", required=True)
    cli.add_argument("--defaults-attempt", required=True)
    cli.add_argument("--number", required=True)
    opts = cli.parse_args(argv)
    if (not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", opts.run)
            or not all(re.fullmatch(r"attempt_\d{3,}", value)
                       for value in (opts.save_attempt, opts.defaults_attempt))):
        cli.error("invalid run or attempt")
    root = ROOT / "automation/runs" / opts.run
    prior = root / opts.save_attempt
    plan = json.loads(read_json(prior / "evidence/draft_plan.json"))
    candidate = json.loads(read_json(prior / "save_observation.json"))["identity"]
    previous = json.loads(read_json(prior / "save_result.json"))
    UUID(candidate["uuid"])
    if (candidate["biz_number"] != opts.number or plan["task_id"] != opts.run
            or candidate["status"] != "编制中" or previous["status"] != "SAVE_UNCERTAIN"):
        cli.error("candidate, task, or prior save outcome is not an exact match")
    defaults = evidence_defaults(root / opts.defaults_attempt / "evidence/new_form_layout.json")
    probe = EvectionProbe(SimpleNamespace(run=opts.run, doc_id=opts.number, expect_name=plan["operator"],
                          observe=True, force_scan=False, tech_budget=180, login_wait=0,
                          wall_cap=300, fill_plan=None, login_only=True))
    ctrl = EvectionSaveController(plan, None, probe.attempt, plan["operator"],
                                   journal_dir=ROOT / "automation/task-registry")
    try:
        start = json.loads(read_json(ctrl.journal))
        if (start["status"] != "SAVE_UNCERTAIN" or start["plan_hash"] != ctrl.plan_hash
                or start["config_sha256"] != ctrl.config_sha256 or ctrl._preflight()):
            raise ValueError("prior save journal or its sources changed; no live attempt")
        probe.acquire_lock()
        if not state_usable(SESSION_STATE):
            raise ValueError("WAIT_HUMAN_LOGIN")
        probe._launch()
        principal = probe.authenticate()
        ctrl.adapter = ReadOnlyAdapter(probe, plan, principal, defaults, candidate)
        save_json(probe, "reconcile_identity.json", candidate)
        result = ctrl.run()
        probe.result["save_identity"] = result.get("identity") or result.get("pending_identity")
        probe.deliver(result["status"], result.get("reason"), result["status"])
        return 0 if result["status"] == "SUCCESS_DRAFT_SAVED" else 2
    except Exception as exc:
        probe.deliver("SAVE_UNCERTAIN", str(exc).splitlines()[0][:200], "SAVE_UNCERTAIN")
        return 2
    finally:
        probe._close_browser()
        probe.release_lock()
        probe.budget.close()


if __name__ == "__main__":
    raise SystemExit(main())
