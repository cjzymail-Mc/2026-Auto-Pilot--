"""Raw UIA subtree dump of a window handle, using Windows-MCP's uia wrapper.

Usage (must run in the Windows-MCP venv):
    cd Windows-MCP && uv run python ../wmcp_rawdump.py <handle> <out-file> [max-depth] [max-nodes]

Dumps Name / ClassName / ControlType / AutomationId / bounding rect recursively.
Pure read via UIA COM — no input events, no writes.
"""

import sys

sys.path.insert(0, "src")

from windows_mcp.uia import ControlFromHandle  # noqa: E402

MAX_NODES_DEFAULT = 1200


def main():
    handle = int(sys.argv[1])
    out_file = sys.argv[2]
    max_depth = int(sys.argv[3]) if len(sys.argv) > 3 else 14
    max_nodes = int(sys.argv[4]) if len(sys.argv) > 4 else MAX_NODES_DEFAULT

    root = ControlFromHandle(handle)
    lines = []
    stats = {"nodes": 0, "named": 0, "types": {}}

    def dump(ctrl, depth, prefix):
        if stats["nodes"] >= max_nodes or depth > max_depth:
            return
        stats["nodes"] += 1
        try:
            name = (ctrl.Name or "").replace("\n", " ").replace("\r", "")[:80]
            cls = ctrl.ClassName or ""
            ctype = ctrl.ControlTypeName
            aid = ctrl.AutomationId or ""
            rect = ctrl.BoundingRectangle
            box = f"({int(rect.left)},{int(rect.top)},{int(rect.right)},{int(rect.bottom)})"
        except Exception as e:
            lines.append(f"{prefix}<error reading element: {e}>")
            return
        if name:
            stats["named"] += 1
        stats["types"][ctype] = stats["types"].get(ctype, 0) + 1
        lines.append(
            f"{prefix}[{ctype}] name='{name}' class='{cls}' aid='{aid}' rect={box}"
        )
        try:
            children = ctrl.GetChildren()
        except Exception as e:
            lines.append(f"{prefix}  <error enumerating children: {e}>")
            return
        for ch in children or []:
            dump(ch, depth + 1, prefix + "  ")

    dump(root, 0, "")

    summary = [
        f"handle={handle} max_depth={max_depth} nodes={stats['nodes']} named={stats['named']}",
        f"control_type_histogram={sorted(stats['types'].items(), key=lambda kv: -kv[1])}",
        "=" * 60,
    ]
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(summary + lines))
    print(f"DUMP OK nodes={stats['nodes']} named={stats['named']} -> {out_file}")


if __name__ == "__main__":
    main()
