"""运行期 WeFlow 启动辅助。"""
from __future__ import annotations

import subprocess
import time
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def is_local_weflow_url(url: str) -> bool:
    """仅允许自动启动本机 WeFlow，避免误处理远程 API。"""
    host = urlparse(url).hostname
    return host in {"127.0.0.1", "localhost", "::1"}


def probe_weflow_api(url: str, token: str | None = None, timeout: float = 1.5) -> bool:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        request = Request(f"{url.rstrip('/')}/health", headers=headers, method="GET")
        with urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except (HTTPError, URLError, TimeoutError, OSError):
        return False


def candidate_weflow_executables() -> list[Path]:
    roots: list[Path] = []
    for env_name in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        value = os.environ.get(env_name)
        if value:
            roots.append(Path(value))

    candidates: list[Path] = []
    for root in roots:
        for relative in (
            "Programs/WeFlow/WeFlow.exe",
            "Programs/WeFlowPortable/app/WeFlow.exe",
            "WeFlow/WeFlow.exe",
            "WeFlowPortable/app/WeFlow.exe",
        ):
            path = root / relative
            if path.exists():
                candidates.append(path)
    return candidates


def launch_weflow() -> Path | None:
    """启动已安装的 WeFlow，返回启动的可执行文件路径。"""
    for exe in candidate_weflow_executables():
        subprocess.Popen(
            [str(exe)],
            cwd=str(exe.parent),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return exe
    return None


def ensure_weflow_api(
    url: str,
    token: str | None = None,
    *,
    wait_seconds: float = 8.0,
    poll_interval: float = 0.5,
) -> tuple[bool, str]:
    """确保本机 WeFlow API 可用；必要时启动 WeFlow 并等待 API 就绪。"""
    if probe_weflow_api(url, token):
        return True, "running"

    if not is_local_weflow_url(url):
        return False, "remote-unavailable"

    launched = launch_weflow()
    if not launched:
        return False, "executable-not-found"

    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if probe_weflow_api(url, token):
            return True, f"started:{launched}"
        time.sleep(poll_interval)

    if probe_weflow_api(url, token):
        return True, f"started:{launched}"

    return False, f"started-but-api-unavailable:{launched}"
