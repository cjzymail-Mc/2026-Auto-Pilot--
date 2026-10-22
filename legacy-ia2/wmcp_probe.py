"""Stdio MCP client probe for Windows-MCP.

Usage:
    python wmcp_probe.py <mode> [args]
    modes:
        tools   - initialize handshake + tools/list, save to wmcp_tools.json
        call <ToolName> <json-args-file> <out-file> - call one tool, save raw result
        chain <steps-json> - run several tools/call in ONE server session.
            steps-json: {"steps": [{"tool": "...", "args": {...}, "out": "f.txt"}, ...]}
            ("out" optional; text content saved UTF-8. Sequence stops on first isError.)

All output written as UTF-8 files (console may be GBK). ASCII-only console prints.
"""

import json
import os
import subprocess
import sys
import threading
import time

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Windows-MCP")
ENV = {
    **os.environ,
    "ANONYMIZED_TELEMETRY": "false",
    "WINDOWS_MCP_DISABLE_FLASH": "1",
    "PYTHONIOENCODING": "utf-8",
}


class McpStdioClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            ["uv", "run", "windows-mcp", "serve"],
            cwd=REPO,
            env=ENV,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._id = 0
        self._stderr_tail = []
        threading.Thread(target=self._drain_stderr, daemon=True).start()

    def _drain_stderr(self):
        for line in self.proc.stderr:
            if len(self._stderr_tail) > 200:
                self._stderr_tail.pop(0)
            self._stderr_tail.append(line.rstrip())

    def stderr_tail(self):
        return "\n".join(self._stderr_tail[-40:])

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _read_msg(self, want_id, timeout):
        """Read stdout lines until JSON-RPC response with matching id arrives."""
        deadline = time.time() + timeout
        result_holder = {}

        def reader():
            for line in self.proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get("id") == want_id:
                    result_holder["msg"] = msg
                    return

        t = threading.Thread(target=reader, daemon=True)
        t.start()
        t.join(timeout=max(0.1, deadline - time.time()))
        return result_holder.get("msg")

    def request(self, method, params=None, timeout=60):
        self._id += 1
        rid = self._id
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        msg = self._read_msg(rid, timeout)
        if msg is None:
            raise TimeoutError(f"no response for {method} (id={rid}) in {timeout}s")
        if "error" in msg:
            raise RuntimeError(f"{method} error: {msg['error']}")
        return msg["result"]

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def initialize(self):
        res = self.request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "wmcp-probe", "version": "0.1.0"},
            },
            timeout=90,
        )
        self.notify("notifications/initialized")
        return res

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def write_utf8(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "tools"
    client = McpStdioClient()
    try:
        init = client.initialize()
        print("INIT OK server =", json.dumps(init.get("serverInfo", {}), ensure_ascii=True))
        if mode == "tools":
            tools = client.request("tools/list", timeout=30)
            write_utf8(
                os.path.join(REPO, "..", "wmcp_tools.json"),
                json.dumps(tools, ensure_ascii=False, indent=2),
            )
            names = [t["name"] for t in tools.get("tools", [])]
            print("TOOLS(%d): %s" % (len(names), ", ".join(names)))
        elif mode == "call":
            tool = sys.argv[2]
            args_file = sys.argv[3]
            out_file = sys.argv[4]
            with open(args_file, encoding="utf-8") as f:
                args = json.load(f)
            t0 = time.time()
            res = client.request(
                "tools/call", {"name": tool, "arguments": args}, timeout=900
            )
            dt = time.time() - t0
            parts = []
            for c in res.get("content", []):
                if c.get("type") == "text":
                    parts.append(c.get("text", ""))
                else:
                    parts.append(f"<content type={c.get('type')}>")
            write_utf8(out_file, "\n".join(parts))
            print(f"CALL {tool} OK in {dt:.1f}s, {len(parts)} parts, saved -> {out_file}")
        elif mode == "chain":
            steps_file = sys.argv[2]
            with open(steps_file, encoding="utf-8") as f:
                steps = json.load(f)["steps"]
            for idx, step in enumerate(steps, 1):
                tool = step["tool"]
                args = step.get("args", {})
                out_file = step.get("out")
                t0 = time.time()
                res = client.request(
                    "tools/call", {"name": tool, "arguments": args}, timeout=900
                )
                dt = time.time() - t0
                parts = []
                for c in res.get("content", []):
                    if c.get("type") == "text":
                        parts.append(c.get("text", ""))
                    else:
                        parts.append(f"<content type={c.get('type')}>")
                text = "\n".join(parts)
                if out_file:
                    write_utf8(out_file, text)
                status = "ERROR" if res.get("isError") else "OK"
                print(
                    f"STEP {idx}/{len(steps)} {tool} {status} in {dt:.1f}s"
                    + (f", saved -> {out_file}" if out_file else "")
                )
                if res.get("isError"):
                    print(f"STEP {idx} error text: {text[:400]}")
                    break
        else:
            raise SystemExit(f"unknown mode {mode}")
    finally:
        client.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback

        traceback.print_exc()
        sys.exit(1)
