"""Compatibility entry point; implementation: tools.verification.probe_selftest."""
from importlib import import_module
import sys

if __name__ == "__main__":
    import runpy
    runpy.run_module("tools.verification.probe_selftest", run_name="__main__")
else:
    sys.modules[__name__] = import_module("tools.verification.probe_selftest")
