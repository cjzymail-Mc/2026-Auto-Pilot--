"""Reproduce selection-blocked output in an isolated hidden test console.

Only the worker's own console receives messages; never attach to another process.
"""
import ctypes
from ctypes import wintypes as w
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time

root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("watch", root / "feature03-自动审批快递单/approval_watch.py")
watch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watch)
k = ctypes.WinDLL("kernel32", use_last_error=True)
u = ctypes.WinDLL("user32", use_last_error=True)
k.GetConsoleWindow.restype = w.HWND
k.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, w.LPVOID, w.DWORD, w.DWORD, w.HANDLE]
k.CreateFileW.restype = w.HANDLE
k.SetStdHandle.argtypes = [w.DWORD, w.HANDLE]
k.GetConsoleMode.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
k.SetConsoleMode.argtypes = [w.HANDLE, w.DWORD]
k.WriteConsoleW.argtypes = [w.HANDLE, w.LPCWSTR, w.DWORD, ctypes.POINTER(w.DWORD), w.LPVOID]
k.CloseHandle.argtypes = [w.HANDLE]
u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
u.PostMessageW.restype = w.BOOL


class Coord(ctypes.Structure):
    _fields_ = [("x", w.SHORT), ("y", w.SHORT)]


class Rect(ctypes.Structure):
    _fields_ = [("left", w.SHORT), ("top", w.SHORT), ("right", w.SHORT), ("bottom", w.SHORT)]


class Selection(ctypes.Structure):
    _fields_ = [("flags", w.DWORD), ("anchor", Coord), ("rectangle", Rect)]


k.GetConsoleSelectionInfo.argtypes = [ctypes.POINTER(Selection)]
hwnd = k.GetConsoleWindow()
if not hwnd:
    raise RuntimeError("Worker needs its own CREATE_NEW_CONSOLE")
input_handle = k.CreateFileW("CONIN$", 0xC0000000, 3, None, 3, 0, None)
output_handle = k.CreateFileW("CONOUT$", 0xC0000000, 3, None, 3, 0, None)
if input_handle == w.HANDLE(-1).value or output_handle == w.HANDLE(-1).value:
    raise ctypes.WinError(ctypes.get_last_error())
k.SetStdHandle(w.DWORD(-10), input_handle)


def selection_flags():
    info = Selection()
    if not k.GetConsoleSelectionInfo(ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    return info.flags


def select_test_console():
    # Hidden windows cannot receive genuine focused mouse input. The console's
    # Mark menu command exercises the same selection/output pause mechanism.
    # This is test-only, targeted at the worker's own hidden HWND.
    if not u.PostMessageW(hwnd, 0x0112, 0xFFF2, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    time.sleep(.15)
    return selection_flags()


def clear_test_selection():
    u.PostMessageW(hwnd, 0x0100, 0x1B, 1)  # Esc to this test console only
    u.PostMessageW(hwnd, 0x0101, 0x1B, 0xC0000001)
    time.sleep(.1)


def write_status():
    written = w.DWORD()
    text = "synthetic pending task\r\n"
    if not k.WriteConsoleW(output_handle, text, len(text), ctypes.byref(written), None):
        raise ctypes.WinError(ctypes.get_last_error())


window_class = ctypes.create_unicode_buffer(256)
u.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
u.GetClassNameW(hwnd, window_class, 256)
report = {"window_class": window_class.value}
try:
    mode = w.DWORD()
    if not k.GetConsoleMode(input_handle, ctypes.byref(mode)):
        raise ctypes.WinError(ctypes.get_last_error())
    if not k.SetConsoleMode(input_handle, mode.value | 0xC0):
        raise ctypes.WinError(ctypes.get_last_error())
    write_status()
    report["before_selection_flags"] = select_test_console()
    writer = threading.Thread(target=write_status, daemon=True)
    writer.start()
    writer.join(.25)
    report["before_output_blocked"] = writer.is_alive()
    clear_test_selection()
    writer.join(2)
    if writer.is_alive():
        raise RuntimeError("Could not clear isolated baseline selection")

    report["configuration"] = watch.disable_console_quick_edit()
    report["after_attempts"] = []
    for _ in range(3):
        flags = selection_flags()
        writer = threading.Thread(target=write_status, daemon=True)
        writer.start()
        writer.join(.25)
        report["after_attempts"].append({"selection_flags": flags, "output_blocked": writer.is_alive()})
        clear_test_selection()
        writer.join(2)
finally:
    clear_test_selection()
    k.CloseHandle(input_handle)
    k.CloseHandle(output_handle)
    Path(sys.argv[1]).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
