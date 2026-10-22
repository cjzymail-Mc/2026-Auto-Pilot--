"""IA2 accessibility probe for a CEF (Chromium Embedded) host inside a window.

Usage (run inside Windows-MCP venv):
    cd Windows-MCP && uv run python ../wmcp_ia2_probe.py <top-hwnd> <out-file>

Steps (all read-only queries):
  1. EnumChildWindows to find Chrome_RenderWidgetHostHWND under the top window.
  2. AccessibleObjectFromWindow(OBJID_CLIENT) on the render HWND — the same
     query a screen reader makes; Chromium typically enables its accessibility
     tree (and web DOM) on first such query.
  3. Walk the IAccessible tree directly, dump name/role/value/location.
"""

import sys
import time

sys.path.insert(0, "src")

import ctypes  # noqa: E402
from ctypes import wintypes  # noqa: E402

from windows_mcp.tree.ia2 import (  # noqa: E402
    _accessible_object_from_window,
    _acc_child_count,
    _acc_location,
    _acc_name,
    _acc_role,
    _acc_state,
    _acc_value,
    _iaccessible,
    _iter_children,
    role_name,
)

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def enum_child_hwnds(top):
    found = []

    def cb(hwnd, _lparam):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        found.append((hwnd, buf.value))
        return True

    user32.EnumChildWindows(top, WNDENUMPROC(cb), 0)
    return found


def main():
    top = int(sys.argv[1])
    out_file = sys.argv[2]
    lines = []

    children = enum_child_hwnds(top)
    cef_hwnds = [h for h, cls in children if "Chrome_RenderWidgetHostHWND" in cls]
    lines.append(f"top hwnd={top} total_child_hwnds={len(children)}")
    for h, cls in children:
        lines.append(f"  child hwnd={h} class={cls}")

    targets = cef_hwnds or [top]
    lines.append(f"render_hwnds={[h for h in cef_hwnds] or 'NONE, falling back to top'}")

    for hwnd in targets:
        lines.append("=" * 60)
        lines.append(f"probing AccessibleObjectFromWindow hwnd={hwnd}")
        t0 = time.time()
        try:
            iacc = _accessible_object_from_window(hwnd)
            iface = _iaccessible()
        except Exception as e:
            lines.append(f"  FAILED: {type(e).__name__}: {e}")
            continue
        lines.append(f"  got IAccessible in {time.time()-t0:.2f}s")

        stats = {"nodes": 0, "named": 0, "roles": {}}
        max_nodes = 1500

        def walk(acc, iface_, depth, prefix):
            if stats["nodes"] >= max_nodes or depth > 40:
                return
            stats["nodes"] += 1
            try:
                name = (_acc_name(acc) or "").replace("\n", " ")[:90]
                role = role_name(_acc_role(acc))
                val = (_acc_value(acc) or "").replace("\n", " ")[:60]
                loc = _acc_location(acc)
                state = _acc_state(acc)
            except Exception as e:
                lines.append(f"{prefix}<err {e}>")
                return
            if name:
                stats["named"] += 1
            stats["roles"][role] = stats["roles"].get(role, 0) + 1
            lines.append(
                f"{prefix}[{role}] '{name}'" + (f" val='{val}'" if val else "")
                + (f" loc={loc}" if loc else "")
            )
            try:
                kids = list(_iter_children(acc, iface_))
            except Exception as e:
                lines.append(f"{prefix}  <enum err {e}>")
                return
            for k in kids:
                walk(k, iface_, depth + 1, prefix + "  ")

        walk(iacc, iface, 0, "")
        lines.append(
            f"SUMMARY hwnd={hwnd}: nodes={stats['nodes']} named={stats['named']} "
            f"roles={sorted(stats['roles'].items(), key=lambda kv: -kv[1])[:12]}"
        )

    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"IA2 PROBE done -> {out_file}")


if __name__ == "__main__":
    main()
