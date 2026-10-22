#!/usr/bin/env python3
"""一键启动 BPM 报销单填写轮（只填不存）。

固化 attempt_024 验证过的启动命令，免去新会话考古。预期耗时：填写 ~4 分钟（238s 确定性）+ keep-open 驻留。
用法：python fill_once.py [探针额外参数原样透传，如 --keep-open-minutes 90]
规则：改过 stage1_browser_probe.py 必须先跑 stage1_probe_selftest.py 再来（README 运行须知）。
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
RUN = "20261021-131724-1c1aadbd"  # 主线 run（23 个 attempt 的证据链在此，attempt 自动递增）


def main():
    os.chdir(ROOT)  # 探针要求 cwd=仓库根（相对路径依赖）
    plan = os.path.join("automation", "runs", RUN, "fill_plan.json")
    if not os.path.exists(plan):
        sys.exit(f"[fill_once] fill_plan 缺失: {plan}")
    ss = os.path.join("automation", ".pw-profile", "session_state.json")
    age_h = (time.time() - os.path.getmtime(ss)) / 3600 if os.path.exists(ss) else 99.0
    if age_h > 3.5:
        print(f"[fill_once][warn] 登录态已 {age_h:.1f}h（>3.5h），大概率回落扫码（需人工扫）")
    else:
        print(f"[fill_once] 登录态 {age_h:.1f}h 新鲜，预计免扫码直注")
    cmd = [sys.executable, "-X", "utf8", "stage1_browser_probe.py",
           "--run", RUN, "--expect-name", "陈晶", "--fill-plan", plan,
           "--keep-open-minutes", "45"] + sys.argv[1:]
    print("[fill_once]", " ".join(cmd[2:]))
    sys.exit(subprocess.call(cmd))


if __name__ == "__main__":
    main()
