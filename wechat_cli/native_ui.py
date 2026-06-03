"""
原生微信 UI 自动化模块 - 提取自 easyChat 原理
不再依赖外部 easyChat 服务，优先使用 Win32 API 直接操作微信窗口。
"""
import ctypes
import ctypes.wintypes
import sys
import time
import pyperclip
import logging
import asyncio
from dataclasses import dataclass
from typing import Callable, List, Optional
auto = None

logger = logging.getLogger("wechat-cli.native_ui")
ProgressCallback = Optional[Callable[[str, float], None]]
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_RETURN = 0x0D
VK_F = 0x46
VK_V = 0x56
VK_W = 0x57
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
SW_RESTORE = 9


def _ensure_auto():
    global auto
    if auto is None:
        try:
            import uiautomation as loaded_auto
        except ImportError:
            loaded_auto = None
        auto = loaded_auto
    return auto


@dataclass
class Rect:
    left: int
    top: int
    right: int
    bottom: int


class Win32Window:
    def __init__(self, hwnd: int):
        self.hwnd = hwnd

    @property
    def BoundingRectangle(self) -> Rect:
        rect = ctypes.wintypes.RECT()
        ctypes.windll.user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        return Rect(rect.left, rect.top, rect.right, rect.bottom)

    def SetFocus(self) -> None:
        user32 = ctypes.windll.user32
        user32.ShowWindow(self.hwnd, SW_RESTORE)
        user32.SetForegroundWindow(self.hwnd)


def _window_text(hwnd: int) -> str:
    user32 = ctypes.windll.user32
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _find_wechat_window_win32() -> Optional[Win32Window]:
    if sys.platform != "win32":
        return None

    user32 = ctypes.windll.user32
    matches: list[int] = []

    def enum_proc(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            class_name = _class_name(hwnd)
            title = _window_text(hwnd)
            if class_name == "WeChatMainWndForPC":
                matches.append(hwnd)
                return False
            if class_name == "Qt51514QWindowIcon" and "微信" in title:
                matches.append(hwnd)
                return False
            if "微信" == title.strip():
                matches.append(hwnd)
                return False
        except Exception:
            pass
        return True

    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_proc)
    user32.EnumWindows(callback, 0)
    return Win32Window(matches[0]) if matches else None


def _key_down(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)


def _key_up(vk: int) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def _press(vk: int) -> None:
    _key_down(vk)
    _key_up(vk)


def _hotkey(*keys: int) -> None:
    for key in keys:
        _key_down(key)
    for key in reversed(keys):
        _key_up(key)


def _click_win32(x: int, y: int) -> None:
    user32 = ctypes.windll.user32
    user32.SetCursorPos(x, y)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def _send_hotkey_win32(hotkey: str) -> None:
    if hotkey == "{Ctrl}{Alt}w":
        _hotkey(VK_CONTROL, VK_MENU, VK_W)
        return
    logger.warning("不支持的原生唤起快捷键: %s", hotkey)


def _send_keys(keys: str) -> None:
    if sys.platform == "win32":
        if keys == "{Ctrl}f":
            _hotkey(VK_CONTROL, VK_F)
            return
        if keys == "{Ctrl}v":
            _hotkey(VK_CONTROL, VK_V)
            return
        if keys == "{Ctrl}a":
            _hotkey(VK_CONTROL, 0x41)
            return
        if keys == "{Delete}":
            _press(0x2E)
            return
        if keys == "{Enter}":
            _press(VK_RETURN)
            return
    automation = _ensure_auto()
    if not automation:
        raise ImportError("请安装依赖: pip install uiautomation pyperclip")
    automation.SendKeys(keys)


def _click(x: int, y: int) -> None:
    if sys.platform == "win32":
        _click_win32(x, y)
        return
    automation = _ensure_auto()
    if not automation:
        raise ImportError("请安装依赖: pip install uiautomation pyperclip")
    automation.Click(x, y)

class NativeWeChatUI:
    SEARCH_BOX_TIMEOUT = 0.3
    HOTKEY_WAKE_DELAY = 0.3
    SEARCH_OPEN_DELAY = 0.2
    TARGET_PASTE_DELAY = 0.2
    TARGET_SELECT_DELAY = 1.2
    INPUT_FOCUS_DELAY = 0.2

    def __init__(self, hotkey="{Ctrl}{Alt}w", progress: ProgressCallback = None):
        self.hotkey = hotkey
        self._window = None
        self._progress = progress

    def _mark(self, label: str, start: float) -> None:
        elapsed = time.perf_counter() - start
        logger.debug("native send +%.3fs %s", elapsed, label)
        if self._progress:
            self._progress(label, elapsed)

    def _get_window(self):
        """寻找并激活微信窗口"""
        if sys.platform == "win32":
            win32_window = _find_wechat_window_win32()
            if not win32_window:
                _send_hotkey_win32(self.hotkey)
                time.sleep(self.HOTKEY_WAKE_DELAY)
                win32_window = _find_wechat_window_win32()
            if win32_window:
                win32_window.SetFocus()
            # 在 Win32 下不论找没找到都直接返回，绝对不要 fallback 到未初始化 COM 的 uiautomation，避免后台线程永久死锁。
            return win32_window

        automation = _ensure_auto()
        if not automation:
            raise ImportError("请安装依赖: pip install uiautomation pyperclip")

        # 不同微信桌面端版本的顶层窗口类名不同。
        candidates = [
            {"ClassName": "WeChatMainWndForPC"},
            {"ClassName": "Qt51514QWindowIcon", "Name": "微信"},
            {"Name": "微信"},
        ]
        wechat_win = None
        for candidate in candidates:
            window = automation.WindowControl(searchDepth=1, **candidate)
            if window.Exists(0):
                wechat_win = window
                break

        if not wechat_win:
            # 尝试通过快捷键唤起
            automation.SendKeys(self.hotkey)
            time.sleep(self.HOTKEY_WAKE_DELAY)
            for candidate in candidates:
                window = automation.WindowControl(searchDepth=1, **candidate)
                if window.Exists(0):
                    wechat_win = window
                    break

        if wechat_win and wechat_win.Exists(0):
            wechat_win.SetFocus()
            return wechat_win
        return None

    def send_text(self, to_name: str, content: str) -> bool:
        """原生发送逻辑"""
        started_at = time.perf_counter()
        self._mark("开始发送", started_at)
        logger.info("native 发送开始: to=%s content=%s", to_name, content[:120])
        win = self._get_window()
        self._mark("定位并聚焦微信窗口", started_at)
        if not win:
            logger.error("未找到微信窗口")
            return False

        try:
            # 微信 4.x 的 Qt 控件树很深，逐层查找会导致发送耗时飙升。
            # 这里只定位顶层窗口，后续全部走键盘和坐标，避免深度 UIAutomation 扫描。
            _send_keys("{Ctrl}f")
            time.sleep(self.SEARCH_OPEN_DELAY)
            self._mark("打开搜索框", started_at)
            
            # 自定义轻量剪贴板操作，避免 PowerShell 子进程挂起和 pyperclip 死锁
            def _set_clipboard(text: str) -> None:
                import ctypes
                import time
                user32 = ctypes.windll.user32
                kernel32 = ctypes.windll.kernel32
                kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
                kernel32.GlobalAlloc.restype = ctypes.c_void_p
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalUnlock.restype = ctypes.c_int
                user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
                user32.SetClipboardData.restype = ctypes.c_void_p

                for _ in range(3):
                    if user32.OpenClipboard(0):
                        user32.EmptyClipboard()
                        buf = ctypes.create_unicode_buffer(text)
                        size = ctypes.sizeof(buf)
                        handle = kernel32.GlobalAlloc(0x0042, size)
                        if handle:
                            ptr = kernel32.GlobalLock(handle)
                            if ptr:
                                ctypes.memmove(ptr, buf, size)
                                kernel32.GlobalUnlock(handle)
                                user32.SetClipboardData(13, handle) # 13 is CF_UNICODETEXT
                        user32.CloseClipboard()
                        return
                    time.sleep(0.1)

            # 1. 搜索并打开目标会话
            _set_clipboard(to_name)
            _send_keys("{Ctrl}v")
            time.sleep(self.TARGET_PASTE_DELAY)
            self._mark("粘贴目标名称", started_at)
            _send_keys("{Enter}") # 选中第一个结果
            time.sleep(self.TARGET_SELECT_DELAY)
            self._mark("选择目标会话", started_at)

            # 2. 粘贴内容到输入框
            # Qt 版微信内部控件不总是暴露给 UIAutomation，显式点击底部输入区。
            rect = win.BoundingRectangle
            input_x = rect.left + int((rect.right - rect.left) * 0.62)
            input_y = rect.bottom - 95
            _click(input_x, input_y)
            time.sleep(self.INPUT_FOCUS_DELAY)
            self._mark("聚焦消息输入区", started_at)
            
            # 清空输入框内已有残留（可能来自于上一次未发出的消息或者意外切换）
            _send_keys("{Ctrl}a")
            _send_keys("{Delete}")
            time.sleep(0.05)
            
            _set_clipboard(content)
            time.sleep(0.1)  # 留一点时间给操作系统的剪贴板同步
            _send_keys("{Ctrl}v")
            self._mark("粘贴消息内容", started_at)
            
            # 模拟人类粘贴后的一点点阅读/反应时间，避免被判定为机器人的极端快速操作
            time.sleep(0.5)
            
            # 3. 发送
            _send_keys("{Enter}")
            self._mark("触发发送", started_at)
            logger.info("native 发送完成: to=%s elapsed=%.3fs", to_name, time.perf_counter() - started_at)
            
            return True
        except Exception as e:
            logger.error(f"UI 发送失败: {e}")
            self._mark(f"发送异常: {e}", started_at)
            return False

async def native_send_handler(to: str, content: str, progress: ProgressCallback = None):
    """异步包装器"""
    def _send_in_thread() -> bool:
        import sys
        ui = NativeWeChatUI(progress=progress)
        # 如果是 Windows，由于我们已经实现了纯 Win32 的鼠标键盘操作和窗口查找，
        # 就尽量不要在后台线程初始化 uiautomation 的 COM 上下文以避免死锁。
        if sys.platform == "win32":
            try:
                return ui.send_text(to, content)
            except Exception as e:
                logger.error(f"原生 UI 发送失败: {e}")
                return False

        automation = _ensure_auto()
        initializer = getattr(automation, "UIAutomationInitializerInThread", None) if automation else None
        try:
            if initializer:
                with initializer():
                    return ui.send_text(to, content)
            return ui.send_text(to, content)
        except Exception as e:
            logger.error(f"原生 UI 发送失败: {e}")
            return False

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _send_in_thread)
