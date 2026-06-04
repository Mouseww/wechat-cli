"""运行环境诊断工具。"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Optional

WECHAT_PROCESS_NAMES = {"wechat.exe", "weixin.exe"}
XWECHAT_FILES_DIR = Path("E:/OneDrive/xwechat_files")


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _is_xwechat_message_db(path: Path) -> bool:
    suffix = path.stem.removeprefix("message_")
    return suffix.isdigit()


def locate_wechat_db(configured_path: Optional[str] = None) -> Optional[Path]:
    """定位微信消息数据库。"""
    if configured_path:
        path = Path(configured_path).expanduser()
        return path if path.exists() else None

    roots = [
        Path.home() / "Documents" / "WeChat Files",
        Path(os.environ.get("USERPROFILE", "")) / "Documents" / "WeChat Files",
        XWECHAT_FILES_DIR,
    ]

    candidates: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        if not root.exists() or root in seen:
            continue
        seen.add(root)
        if root == XWECHAT_FILES_DIR:
            candidates.extend(
                path
                for path in root.glob("*/db_storage/message/message_*.db")
                if _is_xwechat_message_db(path)
            )
            continue
        candidates.extend(root.glob("**/Msg/Multi/MSG0.db"))
        candidates.extend(root.glob("**/Msg/Multi/MSG.db"))

    if not candidates:
        return None

    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0]


def get_native_driver_status(configured_db_path: Optional[str] = None) -> dict:
    """返回原生驱动的非侵入式环境状态。"""
    has_psutil = _module_available("psutil")
    processes: list[dict] = []
    if has_psutil:
        import psutil

        for proc in psutil.process_iter(["pid", "name"]):
            name = proc.info.get("name") or ""
            if name.lower() in WECHAT_PROCESS_NAMES:
                processes.append({"pid": proc.info.get("pid"), "name": name})

    db_path = locate_wechat_db(configured_db_path)
    dependencies = {
        "psutil": has_psutil,
        "pyperclip": _module_available("pyperclip"),
        "uiautomation": _module_available("uiautomation"),
        "pycryptodome": _module_available("Crypto.Cipher")
        or _module_available("Cryptodome.Cipher"),
    }

    is_windows = sys.platform == "win32"
    wechat_running = len(processes) > 0
    db_found = db_path is not None
    db_format = "unknown"
    if db_path:
        db_format = "xwechat" if "db_storage" in db_path.parts else "legacy"
    send_ready = (
        is_windows
        and wechat_running
        and dependencies["pyperclip"]
    )
    read_ready = (
        is_windows
        and wechat_running
        and db_found
        and db_format == "legacy"
        and dependencies["psutil"]
        and dependencies["pycryptodome"]
    )

    return {
        "platform": sys.platform,
        "is_windows": is_windows,
        "dependencies": dependencies,
        "wechat_running": wechat_running,
        "wechat_processes": processes,
        "db_found": db_found,
        "db_path": str(db_path) if db_path else None,
        "db_format": db_format,
        "send_ready": send_ready,
        "read_ready": read_ready,
        "ready": send_ready or read_ready,
    }
