"""In-process diagnostic for the CEF patch disappearing inside Snapshot.

Run from inside the Windows-MCP repo:
    cd Windows-MCP && uv run python ../wmcp_diag.py

Produces (UTF-8, in the parent dir):
  wmcp_diag_run1.log      — DEBUG log of the full Desktop.get_state pass (real path)
  wmcp_diag_summary.txt   — budget state + marker counts for both passes
  wmcp_diag_run2.log      — DEBUG log of the WeCom-only TreeService.get_state pass

Pass 1 reproduces the exact Snapshot tree path (active window first, then
set-ordered others, shared 500-element budget).
Pass 2 resets the budget and asks the tree service for the WeCom window alone,
which should show the CEF IA2 merge firing if the patch itself works.
"""

import logging
import sys
import time

sys.path.insert(0, "src")

WECOM_HWND = 133590

LOG1 = "../wmcp_diag_run1.log"
LOG2 = "../wmcp_diag_run2.log"
SUMMARY = "../wmcp_diag_summary.txt"

MARKERS = ["企业微信", "新增报销", "报销单", "保存", "发送", "申请人", "报销明细", "WeWork"]


def setup_log(path):
    handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = [handler]


def budget_line(ts):
    b = ts.element_budget
    return f"budget count={b.count} limit={b.limit} truncated={b.truncated} exhausted={b.exhausted}"


def marker_counts(sem, tag, lines):
    lines.append(f"[{tag}] semantic_tree chars={len(sem)}")
    for m in MARKERS:
        lines.append(f"[{tag}] marker {m!r}: {sem.count(m)}")


def main():
    from windows_mcp.desktop.service import Desktop

    lines = []

    # ---- Pass 1: real full-desktop path (what Snapshot does) ----
    setup_log(LOG1)
    d = Desktop()
    t0 = time.time()
    state = d.get_state(
        use_vision=False, use_dom=False, use_annotation=False,
        use_ui_tree=True, as_bytes=False,
    )
    elapsed = time.time() - t0
    lines.append(f"=== Pass 1 (full Desktop.get_state) done in {elapsed:.1f}s ===")
    lines.append(budget_line(d.tree))
    marker_counts(state.tree_state.semantic_tree_to_string(), "pass1", lines)

    # ---- Pass 2: WeCom window alone (budget resets per get_state) ----
    setup_log(LOG2)
    t0 = time.time()
    ts2 = d.tree.get_state(WECOM_HWND, [], use_dom=False)
    elapsed = time.time() - t0
    lines.append(f"=== Pass 2 (tree.get_state WeCom only) done in {elapsed:.1f}s ===")
    lines.append(budget_line(d.tree))
    marker_counts(ts2.semantic_tree_to_string(), "pass2", lines)

    with open(SUMMARY, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("DIAG done")


if __name__ == "__main__":
    main()
