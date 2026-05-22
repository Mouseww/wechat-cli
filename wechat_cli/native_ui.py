"""
原生微信 UI 自动化模块 - 提取自 easyChat 原理
不再依赖外部 easyChat 服务，直接操作 uiautomation
"""
import time
import pyperclip
import logging
import asyncio
from typing import List, Optional

try:
    import uiautomation as auto
except ImportError:
    auto = None

logger = logging.getLogger("wechat-cli.native_ui")

class NativeWeChatUI:
    def __init__(self, hotkey="{Ctrl}{Alt}w"):
        self.hotkey = hotkey
        self._window = None

    def _get_window(self):
        """寻找并激活微信窗口"""
        if not auto:
            raise ImportError("请安装依赖: pip install uiautomation pyperclip")
        
        # 4.0+ 版本的 ClassName 特征
        wechat_win = auto.WindowControl(searchDepth=1, ClassName="WeChatMainWndForPC")
        if not wechat_win.Exists(0):
            # 尝试通过快捷键唤起
            auto.SendKeys(self.hotkey)
            time.sleep(0.5)
            wechat_win = auto.WindowControl(searchDepth=1, ClassName="WeChatMainWndForPC")
        
        if wechat_win.Exists(0):
            wechat_win.SetFocus()
            return wechat_win
        return None

    def send_text(self, to_name: str, content: str) -> bool:
        """原生发送逻辑"""
        win = self._get_window()
        if not win:
            logger.error("未找到微信窗口")
            return False

        try:
            # 1. 切换到聊天页签 (ClassName 是 4.0+ 的特征)
            chat_tab = win.ButtonControl(Name="聊天", Depth=6)
            if chat_tab.Exists(0):
                chat_tab.Click(simulateMove=False)

            # 2. 点击搜索框
            search_box = win.EditControl(Name="搜索", Depth=14)
            search_box.Click(simulateMove=False)
            
            # 3. 输入目标名称
            pyperclip.copy(to_name)
            auto.SendKeys("{Ctrl}v")
            time.sleep(0.3)
            auto.SendKeys("{Enter}") # 选中第一个结果

            # 4. 粘贴内容到输入框
            # 4.0+ 的输入框通常是一个包含在某处的 EditControl
            input_box = win.EditControl(Name=to_name, searchDepth=15) 
            # 如果按名称找不准，通常直接 SendKeys 即可，因为 Enter 后焦点就在输入框
            pyperclip.copy(content)
            auto.SendKeys("{Ctrl}v")
            
            # 5. 发送 (支持点击按钮或 Enter)
            send_btn = win.ButtonControl(Name="发送", Depth=21)
            if send_btn.Exists(0):
                send_btn.Click(simulateMove=False)
            else:
                auto.SendKeys("{Enter}")
            
            return True
        except Exception as e:
            logger.error(f"UI 发送失败: {e}")
            return False

async def native_send_handler(to: str, content: str):
    """异步包装器"""
    ui = NativeWeChatUI()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ui.send_text, to, content)
