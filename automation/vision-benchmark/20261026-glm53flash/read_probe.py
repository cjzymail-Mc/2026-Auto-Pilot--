"""Verify the normal agent Read-image route on the explicitly authorized R01.

File tools are confined to inputs/. No PDF, source facts or golden file can be read.
Recorded image blocks retain hashes/lengths only, never base64 payloads.
"""
import base64
import hashlib
import json
import os
import shlex
import subprocess
import time

import benchmark as b

target = b.RESULTS / "R01-glm-5.3-flash-read.json"
if target.exists():
    raise SystemExit("Read-route probe already exists; preserve the prior evidence.")
case = next(c for c in json.loads((b.HERE / "golden.json").read_text(encoding="utf-8"))["cases"] if c["id"] == "R01")
prompt = "先使用Read工具读取当前目录中R01.png这张图片，只读这一个文件；然后完成以下提取。\n" + b.prompt_for(case).replace("禁止调用工具、", "禁止调用其他工具、")
args = ["claude-glm", "--safe-mode", "--restricted", "--setting-sources", "",
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--tools", "Read",
        "--allowedTools", "Read", "--disable-slash-commands", "--model", "glm-5.3-flash",
        "--no-session-persistence", "--input-format", "stream-json", "--output-format", "stream-json",
        "--verbose", "--max-budget-usd", "1", "--system-prompt",
        "Read the one requested local image exactly once using Read. Extract only visible facts. Return the requested JSON and do not guess missing text.", "-p"]
command = "source ~/.bashrc; " + shlex.join(args)
message = {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": prompt}]}}
env = os.environ.copy()
env.pop("CLAUDECODE", None)
b.event(action="read_route_started", case="R01", model="glm-5.3-flash", authorization="explicit user consent for R01 image to api.z.ai")
started = time.monotonic()
print("START Read route R01 glm-5.3-flash", flush=True)
proc = subprocess.run([b.BASH, "--noprofile", "--norc", "-c", command],
                      input="1\n" + json.dumps(message, ensure_ascii=False) + "\n",
                      capture_output=True, text=True, encoding="utf-8", errors="replace",
                      env=env, cwd=b.INPUTS, timeout=180)
images = []


def sanitized(value):
    if isinstance(value, list):
        return [sanitized(x) for x in value]
    if isinstance(value, dict):
        if value.get("type") == "image" and isinstance(value.get("source"), dict):
            src = value["source"]
            data = src.get("data")
            meta = {"type": src.get("type"), "media_type": src.get("media_type"), "data_omitted": True}
            if data:
                binary = base64.b64decode(data)
                meta.update(bytes=len(binary), sha256=hashlib.sha256(binary).hexdigest())
            images.append(meta)
            return {"type": "image", "source_metadata": meta}
        return {k: sanitized(v) for k, v in value.items()}
    return value


records = []
for line in proc.stdout.splitlines():
    try:
        record = json.loads(line)
    except ValueError:
        continue
    if not isinstance(record, dict):
        continue
    if record.get("type") == "system" and record.get("subtype") not in ["init"]:
        continue
    if record.get("type") in ["assistant", "user", "result", "system"]:
        records.append(sanitized(record))
tools = []
models = set()
for rec in records:
    if rec.get("type") == "assistant":
        m = rec.get("message", {})
        if m.get("model"):
            models.add(m["model"])
        tools.extend({"name": x.get("name"), "input": x.get("input")} for x in m.get("content", []) if x.get("type") == "tool_use")
cli_result = next((r for r in reversed(records) if r.get("type") == "result"), {})
result = {"case_id": "R01", "requested_model": "glm-5.3-flash", "route": "Git Bash claude-glm, agent Read tool; initial user message contains text and filename only",
          "prompt": prompt, "at": b.now(), "image_sha256": case["image_sha256"], "exit_code": proc.returncode,
          "elapsed_seconds": round(time.monotonic() - started, 2), "returned_models": sorted(models),
          "tool_calls": tools, "returned_image_blocks": images, "records": records,
          "answer_text": cli_result.get("result"), "cli_result": cli_result}
try:
    answer = b.parse_answer(result["answer_text"] or "")
    result["answer"] = answer
    result["checks"] = [{"field": k, "expected": v, "actual": answer.get(k),
                         "pass": k in answer and b.normalize(k, v) == b.normalize(k, answer.get(k))}
                        for k, v in case["expected"].items()]
    result["score"] = {"correct": sum(x["pass"] for x in result["checks"]), "total": len(result["checks"])}
except Exception as exc:
    result["parse_error"] = type(exc).__name__
b.dump(target, result)
b.event(action="read_route_finished", model="glm-5.3-flash", case="R01", score=result.get("score"),
        tool_names=[x["name"] for x in tools], image_blocks=len(images), elapsed_seconds=result["elapsed_seconds"])
print(json.dumps({k: result.get(k) for k in ["returned_models", "tool_calls", "score", "elapsed_seconds", "parse_error"]}, ensure_ascii=False), flush=True)
print("Returned image blocks:", len(images), flush=True)
