"""One-time, user-authorized retirement of the abandoned round-10 scheduler.

This is an operator maintenance transaction, not a workflow role or continuation.
It preserves original state bytes, including B_RUNNING and failure counts. It
never binds a session, invents a terminal verdict, kills a process, or touches
the business profile/registry. Default invocation only prepares evidence.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes as W
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
RUN = "a7618f4fa0b040fa81782c93eb1bc926"
HELPER = Path(r"C:\Users\xy198\.claude-glm\skills\team-workflow\scripts\workflow.py")
SESSION_DIR = Path(r"C:\Users\xy198\.claude-glm\sessions")
LIVE_FILES = (".team-workflow-state.json", "team-task.md", "team-progress.md",
              "handoff-input.json", "review-input.json", "task-draft.md", "criteria-input.json")


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


K = ctypes.WinDLL("kernel32", use_last_error=True)
NT = ctypes.WinDLL("ntdll")
K.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
K.OpenProcess.restype = W.HANDLE
K.CloseHandle.argtypes = [W.HANDLE]
K.GetExitCodeProcess.argtypes = [W.HANDLE, ctypes.POINTER(W.DWORD)]
NT.NtQueryInformationProcess.argtypes = [W.HANDLE, W.ULONG, W.LPVOID, W.ULONG, ctypes.POINTER(W.ULONG)]
NT.NtQueryInformationProcess.restype = ctypes.c_long


class UnicodeString(ctypes.Structure):
    _fields_ = [("length", W.USHORT), ("maximum", W.USHORT), ("buffer", ctypes.c_void_p)]


class ProcessEntry(ctypes.Structure):
    _fields_ = [("size", W.DWORD), ("usage", W.DWORD), ("pid", W.DWORD),
                ("heap", ctypes.c_size_t), ("module", W.DWORD), ("threads", W.DWORD),
                ("parent", W.DWORD), ("priority", W.LONG), ("flags", W.DWORD),
                ("exe", W.WCHAR * 260)]


def process_info(pid, command=False):
    h = K.OpenProcess(0x1000, False, pid)
    if not h:
        error = ctypes.get_last_error()
        need(error == 87, "PROCESS_QUERY_DENIED_OR_UNKNOWN: " + str(pid))
        return False, ""
    try:
        exit_code = W.DWORD()
        need(K.GetExitCodeProcess(h, ctypes.byref(exit_code)), "PROCESS_EXIT_QUERY_FAILED")
        if exit_code.value != 259:
            return False, ""
        if not command:
            return True, ""
        size = W.ULONG()
        NT.NtQueryInformationProcess(h, 60, None, 0, ctypes.byref(size))
        need(size.value > 0, "PROCESS_COMMAND_QUERY_FAILED: " + str(pid))
        buf = ctypes.create_string_buffer(size.value)
        status = NT.NtQueryInformationProcess(h, 60, buf, size.value, ctypes.byref(size))
        need(status == 0, "PROCESS_COMMAND_QUERY_FAILED: " + str(pid))
        us = UnicodeString.from_buffer(buf)
        return True, ctypes.wstring_at(us.buffer, us.length // 2)
    finally:
        K.CloseHandle(h)


def process_start(pid):
    """Compare Windows creation FILETIME, so a recycled PID is not an old Claude."""
    h = K.OpenProcess(0x1000, False, pid)
    need(h, "PROCESS_START_QUERY_FAILED")
    try:
        values = [W.FILETIME() for _ in range(4)]
        K.GetProcessTimes.argtypes = [W.HANDLE] + [ctypes.POINTER(W.FILETIME)] * 4
        need(K.GetProcessTimes(h, *(ctypes.byref(v) for v in values)), "PROCESS_START_QUERY_FAILED")
        return str((values[0].dwHighDateTime << 32) | values[0].dwLowDateTime)
    finally:
        K.CloseHandle(h)


def process_inventory(state):
    K.CreateToolhelp32Snapshot.argtypes = [W.DWORD, W.DWORD]
    K.CreateToolhelp32Snapshot.restype = W.HANDLE
    K.Process32FirstW.argtypes = [W.HANDLE, ctypes.POINTER(ProcessEntry)]
    K.Process32NextW.argtypes = [W.HANDLE, ctypes.POINTER(ProcessEntry)]
    snapshot = K.CreateToolhelp32Snapshot(2, 0)
    need(snapshot and snapshot != ctypes.c_void_p(-1).value, "PROCESS_SNAPSHOT_FAILED")
    inspected = []
    try:
        item = ProcessEntry(); item.size = ctypes.sizeof(item)
        found = K.Process32FirstW(snapshot, ctypes.byref(item))
        while found:
            name, pid = item.exe.lower(), item.pid
            if pid != os.getpid() and name in {
                "claude.exe", "python.exe", "pythonw.exe", "node.exe", "chrome.exe", "chromium.exe"
            }:
                alive, cmd = process_info(pid, command=True)
                if alive:
                    old_session = any(sid in cmd for sid in state["sessions"].values())
                    executor = any(x in cmd for x in (
                        "fill_once.py", "stage1_browser_probe.py", "observe_0204.py", "bpm_login.py"))
                    waiter = "workflow.py" in cmd
                    browser = name in {"chrome.exe", "chromium.exe"} and any(
                        x in cmd.lower() for x in ("playwright", ".pw-profile", "bpm.qiaodan.com"))
                    need(not any((old_session, executor, waiter, browser)),
                         "POSSIBLE_LIVE_OLD_EXECUTOR: " + str(pid))
                    # Never persist raw command lines, environment, IPC keys or tokens.
                    inspected.append({"pid": pid, "name": name, "old_executor_match": False})
            found = K.Process32NextW(snapshot, ctypes.byref(item))
    finally:
        K.CloseHandle(snapshot)
    return inspected


def protected_manifest():
    paths = set()
    for relative in ("automation/task-registry", "automation/runs", "automation/document-types",
                     "feature01-细化报销skill/12月公出-发票", ".claude/skills/bpm-fill-run"):
        root = REPO / relative
        paths.update(p for p in root.rglob("*") if p.is_file())
    paths.update(REPO.glob("*.py"))
    paths.update(p for p in (REPO / "automation").glob("*.schema.json"))
    paths.update(p for p in (REPO / "feature01-细化报销skill").glob("*冻结*.md"))
    paths.update(p for p in HERE.parent.rglob("*") if p.is_file() and not p.is_relative_to(HERE))
    return {p.relative_to(REPO).as_posix(): digest(p) for p in sorted(paths)}


def preflight(helper):
    state = helper.load(REPO)
    need(state["run"] == RUN and state["round"] == 10 and state["seq"] == 49
         and state["phase"] == "B_RUNNING", "OLD_STATE_CHANGED")
    need(state["sessions"] == {
        "B": "fb56811d-33fa-4ca7-99e1-82643f913df8",
        "A": "9ba961a6-cceb-4edb-a1d2-8649317482c2"}, "OLD_SESSION_BINDINGS_CHANGED")
    helper.source_ok(REPO, state)
    sessions = []
    for record in SESSION_DIR.glob("*.json"):
        value = json.loads(record.read_text(encoding="utf-8"))
        if value.get("sessionId") in state["sessions"].values():
            alive, _ = process_info(int(value["pid"]))
            current_start = process_start(int(value["pid"])) if alive else None
            if alive:
                need(str(value.get("procStart", "")).isdigit(), "OLD_PROCESS_START_UNKNOWN")
                need(current_start != str(value["procStart"]), "BOUND_SESSION_STILL_ALIVE")
            sessions.append({"pid": value["pid"], "session_id": value["sessionId"],
                             "original_process_alive": False, "pid_reused": alive,
                             "original_process_start": value.get("procStart"),
                             "current_process_start": current_start})
    for role, proof in state["runtime_evidence"].items():
        p = Path(proof["transcript"])
        need(p.is_file() and time.time() - p.stat().st_mtime > 3600,
             "BOUND_TRANSCRIPT_RECENT_OR_MISSING")
    lock = REPO / "automation/.pw-profile/executor.lock"
    lock_hash = digest(lock) if lock.exists() else None
    pid = int(lock.read_text().strip()) if lock.exists() else None
    if pid:
        need(not process_info(pid)[0], "PROFILE_EXECUTOR_STILL_ALIVE")
    for role in state["sessions"]:
        handle = helper.Handle(helper.key(REPO, RUN + "|waiter|" + role), mutex=True)
        acquired = False
        try:
            acquired = handle.wait(0)
            need(acquired, "BOUND_WAITER_STILL_RUNNING")
        finally:
            if acquired:
                handle.api.ReleaseMutex(handle.handle)
            handle.close()
    return state, {"bound_session_records": sessions, "processes": process_inventory(state),
                   "profile_owner_pid": pid, "profile_owner_alive": False,
                   "profile_lock_sha256": lock_hash}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    need(REPO.name == "2026-Auto-Pilot 企业微信" and HERE.is_relative_to(REPO), "WRONG_REPOSITORY")
    spec = importlib.util.spec_from_file_location("original_team_workflow", HELPER)
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    with helper.locked(REPO):
        state, probes = preflight(helper)
        live = {name: digest(REPO / name) for name in LIVE_FILES if (REPO / name).is_file()}
        protected = protected_manifest()
        record = {"operation": "USER_AUTHORIZED_ORPHAN_RETIREMENT", "created": helper.stamp(),
                  "authorization": "用户提供新窗口启动阻断后明确要求：你能直接帮我修复吗？",
                  "actor": "Codex operator maintenance; not an A/B workflow session",
                  "original_run": RUN, "original_phase": state["phase"], "original_round": 10,
                  "original_failure_counts": state["failures"], "original_state_sha256": live[helper.STATE],
                  "helper_sha256": digest(HELPER), "root_files": live, "quiescence": probes,
                  "protected_file_count": len(protected), "business_execution": False,
                  "workflow_success_claimed": False}
        if not args.apply:
            helper.preserve(HERE / "preflight.json", json_bytes(record))
            helper.preserve(HERE / "protected-before.json", json_bytes(protected))
            print(json.dumps({"status": "PREPARED", "root_files": list(live),
                              "protected_files": len(protected), "old_failures": state["failures"]}))
            return
        expected = json.loads((HERE / "preflight.json").read_text(encoding="utf-8"))
        need(expected["root_files"] == live and expected["helper_sha256"] == digest(HELPER),
             "PREFLIGHT_BINDING_CHANGED")
        need(json.loads((HERE / "protected-before.json").read_text(encoding="utf-8")) == protected,
             "PROTECTED_FILES_CHANGED_SINCE_PREFLIGHT")
        for name in live:
            helper.preserve(HERE / "root-files" / name, (REPO / name).read_bytes())
            need(digest(HERE / "root-files" / name) == live[name], "BACKUP_VERIFY_FAILED")
        moved = []
        try:
            destination = HERE / "retired-live"
            destination.mkdir(exist_ok=False)
            # State goes last, under the original helper's mutex: no new init can
            # race with a half-retired root. No old state bytes are rewritten.
            for name in [n for n in live if n != helper.STATE] + [helper.STATE]:
                need(digest(REPO / name) == live[name], "LIVE_FILE_CHANGED")
                os.rename(REPO / name, destination / name)
                moved.append(name)
            need(protected_manifest() == protected, "PROTECTED_DATA_CHANGED")
            lock = REPO / "automation/.pw-profile/executor.lock"
            need((digest(lock) if lock.exists() else None) == probes["profile_lock_sha256"],
                 "PROFILE_LOCK_CHANGED")
            # Validate the unchanged helper's task gate in an isolated fixture.
            with tempfile.TemporaryDirectory(prefix="prepared-task-check-", dir=HERE) as temp:
                fixture = Path(temp)
                (fixture / "team-task.md").write_text(
                    "# 本次任务：从旧成果断点继续真实案例\n\n## done_when\n证据与实际一致。\n", encoding="utf-8")
                helper.prepared_task(fixture)
            for name, expected_hash in live.items():
                need(not (REPO / name).exists() and digest(destination / name) == expected_hash,
                     "RETIREMENT_VERIFY_FAILED")
            record.update(status="RETIRED_NOT_COMPLETED", completed=helper.stamp(),
                          active_state_absent=True, root_task_absent=True, root_progress_absent=True,
                          protected_files_unchanged=True, profile_lock_unchanged=True,
                          original_failure_counts_preserved=True, helper_prepared_task_gate="PASS")
            helper.preserve(HERE / "recovery-result.json", json_bytes(record))
        except BaseException:
            for name in reversed(moved):
                need(not (REPO / name).exists(), "ROLLBACK_ROOT_CONFLICT")
                os.rename(HERE / "retired-live" / name, REPO / name)
            raise
        print(json.dumps({"status": record["status"], "root_files_archived": list(live),
                          "protected_files_unchanged": len(protected), "original_failure_counts": state["failures"],
                          "next": "current GLM window: /team-workflow run <V3 document>"}))


if __name__ == "__main__":
    main()
