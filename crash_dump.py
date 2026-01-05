from __future__ import annotations

import os
import sys
import time
import traceback
import logging
import threading
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


def _now_stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S", time.localtime())


def _safe_mkdir(p: Path):
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _flush_logging():
    try:
        root = logging.getLogger()
        for h in list(getattr(root, "handlers", []) or []):
            try:
                h.flush()
            except Exception:
                pass
    except Exception:
        pass
    try:
        logging.shutdown()
    except Exception:
        pass


def _write_text_file(path: Path, text: str):
    try:
        _safe_mkdir(path.parent)
        path.write_text(text, encoding="utf-8", errors="replace")
    except Exception:
        pass


def _install_python_exception_hooks(dump_dir: Path):
    prev_sys_hook = sys.excepthook

    def _sys_hook(exc_type, exc_value, exc_tb):
        try:
            stamp = _now_stamp()
            trace_txt = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            _write_text_file(dump_dir / f"crash-{stamp}.pytrace.txt", trace_txt)
        except Exception:
            pass
        try:
            logger.critical("Uncaught exception:", exc_info=(exc_type, exc_value, exc_tb))
        except Exception:
            pass
        _flush_logging()
        try:
            if prev_sys_hook and prev_sys_hook is not _sys_hook:
                prev_sys_hook(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _sys_hook

    # Thread exceptions (Python 3.8+)
    if hasattr(threading, "excepthook"):
        prev_thread_hook = threading.excepthook

        def _thread_hook(args):
            try:
                stamp = _now_stamp()
                trace_txt = "".join(
                    traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
                )
                _write_text_file(dump_dir / f"crash-thread-{stamp}.pytrace.txt", trace_txt)
            except Exception:
                pass
            try:
                logger.critical("Uncaught thread exception:", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))
            except Exception:
                pass
            _flush_logging()
            try:
                if prev_thread_hook and prev_thread_hook is not _thread_hook:
                    prev_thread_hook(args)
            except Exception:
                pass

        threading.excepthook = _thread_hook


def _install_faulthandler(dump_dir: Path):
    try:
        import faulthandler

        stamp = _now_stamp()
        p = dump_dir / f"fault-{stamp}.faulthandler.txt"
        _safe_mkdir(dump_dir)
        f = open(p, "w", encoding="utf-8", errors="replace")
        faulthandler.enable(file=f, all_threads=True)
        # Keep file handle referenced globally to avoid GC close
        globals()["_faulthandler_file"] = f
    except Exception:
        pass


def _install_windows_minidump(dump_dir: Path):
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        dbghelp = ctypes.WinDLL("Dbghelp.dll")
        kernel32 = ctypes.WinDLL("kernel32.dll")

        MiniDumpWriteDump = dbghelp.MiniDumpWriteDump
        MiniDumpWriteDump.argtypes = [
            wintypes.HANDLE,  # hProcess
            wintypes.DWORD,   # ProcessId
            wintypes.HANDLE,  # hFile
            wintypes.DWORD,   # DumpType
            ctypes.c_void_p,  # ExceptionParam
            ctypes.c_void_p,  # UserStreamParam
            ctypes.c_void_p,  # CallbackParam
        ]
        MiniDumpWriteDump.restype = wintypes.BOOL

        class MINIDUMP_EXCEPTION_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("ThreadId", wintypes.DWORD),
                ("ExceptionPointers", ctypes.c_void_p),
                ("ClientPointers", wintypes.BOOL),
            ]

        # Reasonable size/utility tradeoff
        MiniDumpWithDataSegs = 0x00000001
        MiniDumpWithHandleData = 0x00000004
        MiniDumpWithThreadInfo = 0x00001000
        MiniDumpWithUnloadedModules = 0x00000020
        dump_type = (
            MiniDumpWithDataSegs
            | MiniDumpWithHandleData
            | MiniDumpWithThreadInfo
            | MiniDumpWithUnloadedModules
        )

        SetUnhandledExceptionFilter = kernel32.SetUnhandledExceptionFilter
        SetUnhandledExceptionFilter.argtypes = [ctypes.c_void_p]
        SetUnhandledExceptionFilter.restype = ctypes.c_void_p

        GetCurrentProcess = kernel32.GetCurrentProcess
        GetCurrentProcess.argtypes = []
        GetCurrentProcess.restype = wintypes.HANDLE

        GetCurrentProcessId = kernel32.GetCurrentProcessId
        GetCurrentProcessId.argtypes = []
        GetCurrentProcessId.restype = wintypes.DWORD

        GetCurrentThreadId = kernel32.GetCurrentThreadId
        GetCurrentThreadId.argtypes = []
        GetCurrentThreadId.restype = wintypes.DWORD

        CreateFileW = kernel32.CreateFileW
        CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        CreateFileW.restype = wintypes.HANDLE

        CloseHandle = kernel32.CloseHandle
        CloseHandle.argtypes = [wintypes.HANDLE]
        CloseHandle.restype = wintypes.BOOL

        GENERIC_WRITE = 0x40000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        CREATE_ALWAYS = 2
        FILE_ATTRIBUTE_NORMAL = 0x00000080

        EXCEPTION_EXECUTE_HANDLER = 1

        @ctypes.WINFUNCTYPE(wintypes.LONG, ctypes.c_void_p)
        def _handler(exception_pointers):
            try:
                stamp = _now_stamp()
                _safe_mkdir(dump_dir)
                dump_path = dump_dir / f"crash-{stamp}.dmp"
                hfile = CreateFileW(
                    str(dump_path),
                    GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                    None,
                    CREATE_ALWAYS,
                    FILE_ATTRIBUTE_NORMAL,
                    None,
                )
                if hfile and hfile != wintypes.HANDLE(-1).value:
                    try:
                        mei = MINIDUMP_EXCEPTION_INFORMATION()
                        mei.ThreadId = GetCurrentThreadId()
                        mei.ExceptionPointers = exception_pointers
                        mei.ClientPointers = False
                        MiniDumpWriteDump(
                            GetCurrentProcess(),
                            GetCurrentProcessId(),
                            hfile,
                            dump_type,
                            ctypes.byref(mei),
                            None,
                            None,
                        )
                    finally:
                        try:
                            CloseHandle(hfile)
                        except Exception:
                            pass
            except Exception:
                pass
            try:
                _flush_logging()
            except Exception:
                pass
            return EXCEPTION_EXECUTE_HANDLER

        # Keep reference to avoid GC
        globals()["_win_unhandled_exception_filter"] = _handler
        SetUnhandledExceptionFilter(_handler)
    except Exception:
        pass


def install_crash_dumps(dump_dir: Path):
    """Install crash dump handlers. Safe to call multiple times."""
    try:
        dump_dir = Path(dump_dir)
    except Exception:
        return
    _safe_mkdir(dump_dir)
    _install_python_exception_hooks(dump_dir)
    _install_faulthandler(dump_dir)
    _install_windows_minidump(dump_dir)


