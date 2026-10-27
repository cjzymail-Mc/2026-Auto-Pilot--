"""Restore a POSIX PATH after Claude Code loads a Windows shell snapshot."""

import os
from pathlib import Path
import sys


MARKER = "# claude-glm Windows PATH normalization (2026-10-09)"
SCRIPT = MARKER + r'''
if [[ ${PATH-} == *';'* ]] && [[ -x /usr/bin/cygpath ]]; then
  if _claude_glm_posix_path=$(/usr/bin/cygpath -u -p "$PATH") && [[ -n $_claude_glm_posix_path ]]; then
    export PATH="$_claude_glm_posix_path"
  fi
  unset _claude_glm_posix_path
fi
'''


def main():
    if os.name != "nt":
        return 0
    env_file = os.environ.get("CLAUDE_ENV_FILE")
    if not env_file:
        print("[claude-glm PATH] CLAUDE_ENV_FILE is unavailable.", file=sys.stderr)
        return 1
    try:
        path = Path(env_file)
        existing = path.read_text(encoding="utf-8") if path.exists() else ""
        if MARKER not in existing:
            with path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write("\n" + SCRIPT)
    except OSError as error:
        print(f"[claude-glm PATH] Cannot write session environment: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
