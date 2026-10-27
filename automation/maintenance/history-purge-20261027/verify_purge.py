"""One-off: scan every blob in git history for known real card numbers (2026-10-27 purge verification).

敏感卡号清单不落 Git：本脚本从仓库外的本地 patterns 文件读取（每行一个号码），
默认位置见 main() 中 DEFAULT_PATTERNS，也可用 --patterns 指定。
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_PATTERNS = Path(__file__).resolve().parents[3] / "2026-Auto-Pilot-企业微信-purged-local-20261027" / "real-card-patterns-20261027.txt"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS,
                    help="本地卡号清单文件（每行一个号码；不入库）")
    args = ap.parse_args()
    if not args.patterns.is_file():
        print(f"patterns file not found: {args.patterns}", file=sys.stderr)
        return 2
    real = re.compile("|".join(
        re.escape(line.strip()) for line in args.patterns.read_text(encoding="utf-8").splitlines() if line.strip()
    ))

    objs = subprocess.run(
        ["git", "cat-file", "--batch-check", "--batch-all-objects"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout.splitlines()
    blobs = [line.split()[0] for line in objs if line.split()[1] == "blob"]
    with tempfile.TemporaryDirectory() as td:
        ids_file = Path(td) / "ids.txt"
        out_file = Path(td) / "out.bin"
        ids_file.write_bytes(("\n".join(blobs) + "\n").encode())
        with ids_file.open("rb") as fin, out_file.open("wb") as fout:
            subprocess.run(["git", "cat-file", "--batch"], stdin=fin, stdout=fout, check=True)
        checked = 0
        bad = []
        with out_file.open("rb") as f:
            while True:
                header = f.readline().decode()
                if not header.strip():
                    break
                parts = header.split()
                oid = parts[0]
                size = int(parts[2]) if len(parts) >= 3 else 0
                data = f.read(size)
                f.read(1)  # trailing newline
                if real.search(data.decode("utf-8", "replace")):
                    bad.append(oid)
                checked += 1
    print(f"blobs checked: {checked}/{len(blobs)}; real-card blobs: {len(bad)}")
    if bad:
        names = subprocess.run(
            ["git", "rev-list", "--all", "--objects"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        ).stdout
        lookup = {}
        for line in names.splitlines():
            parts2 = line.split(" ", 1)
            if len(parts2) == 2:
                lookup[parts2[0]] = parts2[1]
        for oid in bad[:10]:
            print("  LEAK:", oid, lookup.get(oid, "(unreachable)"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
