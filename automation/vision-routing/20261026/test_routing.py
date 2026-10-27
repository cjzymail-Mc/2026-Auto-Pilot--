"""Exercise the installed launcher and genuine 5.3 -> Flash -> 5.3 delegation.

No expected facts are sent to the model. A fresh temporary cwd contains only PNGs.
Parent tools are Agent/Read; the child has Read only. No OA or original PDF access.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BENCH = ROOT / "automation/vision-benchmark/20261026-glm53flash"
BASH = r"C:\Program Files\Git\bin\bash.exe"
OUT = HERE / "results"
OUT.mkdir(exist_ok=True)


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def norm(key, value):
    # Load the existing scorer locally, not in any model subprocess.
    import importlib.util
    spec = importlib.util.spec_from_file_location("vision_benchmark", BENCH / "benchmark.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.normalize(key, value)


def safe(value):
    if isinstance(value, list):
        return [safe(x) for x in value]
    if isinstance(value, dict):
        if value.get("type") == "image" and isinstance(value.get("source"), dict):
            source = value["source"]
            meta = {"type": source.get("type"), "media_type": source.get("media_type"), "data_omitted": True}
            if source.get("data"):
                binary = base64.b64decode(source["data"])
                meta.update(bytes=len(binary), sha256=hashlib.sha256(binary).hexdigest())
            return {"type": "image", "source_metadata": meta}
        return {k: safe(v) for k, v in value.items()}
    return value


def records_from(stdout):
    records = []
    for line in stdout.splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        if d.get("type") == "system" and d.get("subtype") in ["thinking_tokens", "ui_invalidate"]:
            continue
        if d.get("type") in ["system", "assistant", "user", "result"]:
            records.append(safe(d))
    return records


def dry_run():
    syntax = subprocess.run([BASH, "--noprofile", "--norc", "-n", str(Path.home() / ".bashrc")], capture_output=True, text=True, timeout=20)
    assert syntax.returncode == 0, "Bash syntax error"
    probe = str(HERE / "launcher_probe.py").replace("\\", "/")
    evidence = []
    for choice, explicit in [("1", False), ("2", False), ("3", False), ("1", True)]:
        command = "source ~/.bashrc; claude() { python " + shlex.quote(probe) + ' "$@"; }; claude-glm'
        if explicit:
            command += " --model glm-5.3-flash"
        # Bind the choice to the function itself, after shell startup commands.
        command += " <<< " + shlex.quote(choice)
        proc = subprocess.run([BASH, "--noprofile", "--norc", "-c", command], input="", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20)
        found = None
        for line in proc.stdout.splitlines():
            try:
                obj = json.loads(line)
                if obj.get("probe"):
                    found = obj
            except (ValueError, AttributeError):
                continue
        entry = {"choice": choice, "explicit_override": explicit, "exit_code": proc.returncode, "probe": found}
        if found:
            expected = "glm-5.3-flash" if explicit else {"1": "glm-5.3", "2": "deepseek-v4-pro[1m]", "3": "z-ai/glm-5.2"}[choice]
            assert found["main_model_options"] == [expected], entry
            assert bool(found["agents"]) == (choice == "1"), entry
            assert found["has_visual_rules"] == (choice == "1"), entry
            if choice == "1":
                assert found["agents"]["vision-reader"]["model"] == "glm-5.3-flash"
        else:
            entry["limitation"] = "Provider credential prerequisite prevented no-network inspection"
        evidence.append(entry)
    assert evidence[0]["probe"] and evidence[3]["probe"]
    dump(HERE / "launcher-dry-run.json", {"bash_syntax": "pass", "network_calls": 0, "cases": evidence})
    print(json.dumps(evidence, ensure_ascii=False), flush=True)


def run(which, label=""):
    if label and not re.fullmatch(r"[a-zA-Z0-9_-]+", label):
        raise SystemExit("Invalid evidence label")
    target = OUT / f"{which}{('-' + label) if label else ''}.json"
    if target.exists():
        raise SystemExit("Existing evidence retained: " + target.name)
    golden = json.loads((BENCH / "golden.json").read_text(encoding="utf-8"))["cases"]
    workspace = Path(tempfile.mkdtemp(prefix="glm-vision-routing-"))
    if which == "plain":
        prompt = '只处理这个纯文字问题，不读取文件：37+58等于多少？只返回JSON {"sum":数字,"marker":"TEXT_ONLY_OK"}。'
        expected = {"sum": 95, "marker": "TEXT_ONLY_OK"}
        image_sha = None
    else:
        ident = {"synthetic": "S01", "real": "R01"}[which]
        case = next(c for c in golden if c["id"] == ident)
        image = workspace / "sample.png"
        image.write_bytes((BENCH / "inputs" / case["image"]).read_bytes())
        image_sha = hashlib.sha256(image.read_bytes()).hexdigest()
        assert image_sha == case["image_sha256"]
        expected = case["expected"]
        if which == "synthetic":
            prompt = ('读取当前目录sample.png的内容，提取verification_code、invoice_number、total_amount、origin_station、destination_station、red_circle_count、blue_square_count；只返回包含这些字段的JSON。号码和金额用字符串，数量用整数；不可见字段为null。')
        else:
            prompt = ('请读取当前目录sample.png这份材料，提取document_type、document_number、issue_or_apply_date、plate、travel_date_from、travel_date_to、origin_station、destination_station、invoice_codes、invoice_numbers、trip_count、invoice_count、total_amount、total_amount_cn、buyer_name。'
                      'document_type采用trip_summary/toll_invoice/fuel_invoice/unknown；代码与号码用逐票据行对应的数组，保留前导零和重复代码；通行日期与申请日期分开；站名换行要拼接且保留省份前缀。只返回字段JSON，缺失值null。')
    # No --model, --agents, or injected routing prompts here: these must come from installed config/launcher.
    args = ["claude-glm", "--setting-sources", "user", "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
            "--tools", "Agent,Read", "--allowedTools", "Agent,Read", "--disable-slash-commands",
            "--no-session-persistence", "--input-format", "stream-json", "--output-format", "stream-json",
            "--verbose", "--forward-subagent-text", "--max-budget-usd", "2", "-p"]
    command = "source ~/.bashrc; " + shlex.join(args)
    message = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": prompt}]}}
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    # Each temp directory contains only the permitted image, not ground truth or old logs.
    start = time.monotonic()
    print("START", which, flush=True)
    try:
        proc = subprocess.run([BASH, "--noprofile", "--norc", "-c", command], input="1\n" + json.dumps(message, ensure_ascii=False) + "\n",
                              capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, cwd=workspace, timeout=240)
    except subprocess.TimeoutExpired:
        dump(target, {"test": which, "error": "timeout", "elapsed_seconds": round(time.monotonic() - start, 2)})
        print("TIMEOUT", which, flush=True)
        return
    records = records_from(proc.stdout)
    result = {"test": which, "label": label, "at": datetime.now(timezone.utc).isoformat(), "prompt": prompt,
              "workspace": str(workspace), "image_sha256": image_sha, "exit_code": proc.returncode,
              "elapsed_seconds": round(time.monotonic() - start, 2), "records": records,
              "stderr_tail": re.sub(r"(?i)(?:bearer\s+|(?:api[_-]?key|auth[_-]?token)[=: ]+)\S+", "[REDACTED]", proc.stderr[-1200:])}
    messages = []
    tools = []
    for rec in records:
        if rec.get("type") == "assistant":
            msg = rec.get("message", {})
            context = {"model": msg.get("model"), "parent_tool_use_id": rec.get("parent_tool_use_id")}
            messages.append(context)
            for block in msg.get("content", []):
                if block.get("type") == "tool_use":
                    tools.append({**context, "name": block.get("name"), "input": block.get("input")})
    result["assistant_models"] = sorted({m["model"] for m in messages if m["model"]})
    result["message_sequence"] = messages
    result["tool_calls"] = tools
    cli_result = next((r for r in reversed(records) if r.get("type") == "result"), {})
    result["cli_result"] = cli_result
    answer = cli_result.get("result", "")
    result["answer_text"] = answer
    try:
        first, last = answer.find("{"), answer.rfind("}")
        parsed = json.loads(answer[first:last + 1])
        result["answer"] = parsed
        comparisons = [{"field": k, "expected": v, "actual": parsed.get(k), "pass": k in parsed and norm(k, v) == norm(k, parsed.get(k))} for k, v in expected.items()]
        result["checks"] = comparisons
        result["score"] = {"correct": sum(c["pass"] for c in comparisons), "total": len(comparisons)}
    except Exception as exc:
        result["parse_error"] = type(exc).__name__
    result["main_stayed_glm53"] = bool(messages) and all(m["model"] == "glm-5.3" for m in messages if m["parent_tool_use_id"] is None)
    result["main_read_calls"] = sum(t["name"] == "Read" and t["parent_tool_use_id"] is None for t in tools)
    result["vision_delegations"] = sum(t["name"] == "Agent" and (t.get("input") or {}).get("subagent_type") == "vision-reader" for t in tools)
    result["child_flash_messages"] = sum(m["model"] == "glm-5.3-flash" and m["parent_tool_use_id"] is not None for m in messages)
    result["child_read_calls"] = sum(t["name"] == "Read" and t["parent_tool_use_id"] is not None for t in tools)
    dump(target, result)
    print(json.dumps({k:result.get(k) for k in ["test", "assistant_models", "score", "main_stayed_glm53", "main_read_calls", "vision_delegations", "child_flash_messages", "child_read_calls", "elapsed_seconds", "parse_error"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("test", choices=["dry-run", "plain", "synthetic", "real"])
    parser.add_argument("--label", default="")
    args = parser.parse_args()
    dry_run() if args.test == "dry-run" else run(args.test, args.label)
