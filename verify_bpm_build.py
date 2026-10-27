"""Compatibility entry point; implementation: tools.verification.build."""
from importlib import import_module
import sys

if __name__ == "__main__":
    raise SystemExit(import_module("tools.verification.build").main())
else:
    sys.modules[__name__] = import_module("tools.verification.build")
