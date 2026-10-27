"""Compatibility entry point; implementation: bpm.fill_cli."""
from importlib import import_module
import sys

if __name__ == "__main__":
    raise SystemExit(import_module("bpm.fill_cli").main())
else:
    sys.modules[__name__] = import_module("bpm.fill_cli")
