"""Compatibility entry point; implementation: bpm.template."""
from importlib import import_module
import sys

if __name__ == "__main__":
    raise SystemExit(import_module("bpm.template").main())
else:
    sys.modules[__name__] = import_module("bpm.template")
