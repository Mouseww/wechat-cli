"""easyChat UI 自动化发送 - 仅 Windows 可用

发送流程：
1. 搜索联系人/群聊名称
2. 点击进入对话
3. 粘贴消息内容
4. 点击发送

注意：发送用的是显示名称搜索，不是 wxid！
"""
from __future__ import annotations
import asyncio
import logging
from typing import Optional
from .models import SendRequest, SendResponse

logger = logging.getLogger("wechat-cli.easychat")


class EasyChatClient:
    """easyChat 发送客户端（Windows UI 自动化）"""

    def __init__(self, wechat_path: Optional[str] = None, hotkey: str = "{Ctrl}{Alt}w"):
        self.wechat_path = wechat_path
        self.hotkey = hotkey
        self._wechat = None
        self._available = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> bool:
        """初始化 easyChat 连接"""
        async with self._init_lock:
            if self._available:
                return True
            try:
                # 延迟导入，仅在 Windows 上可用
                import sys
                if sys.platform != "win32":
                    logger.warning("easyChat 仅支持 Windows 平台")
                    return False

                import uiautomation as auto
                from versions.wechat_4_1_9_21 import WeChat
                self._wechat = WeChat(self.wechat_path or "")
                if self.hotkey:
                    self._wechat.hotkey = self.hotkey
                self._available = True
                logger.info("easyChat UI 自动化已初始化")
                return True
            except ImportError as e:
                logger.warning(f"easyChat 不可用 (缺少依赖): {e}")
                return False
            except Exception as e:
                logger.error(f"easyChat 初始化失败: {e}")
                return False

    async def send_message(self, req: SendRequest) -> SendResponse:
        """通过 UI 自动化发送消息

        Args:
            req.to: 必须是微信里能搜索到的显示名称（好友备注/昵称 或 群聊名称）
                    不能是 wxid！
        """
        if not self._available:
            if not await self.initialize():
                return SendResponse(
                    success=False,
                    error=(
                        "easyChat 不可用。可能原因：\n"
                        "1. 当前系统不是 Windows\n"
                        "2. 未安装 easyChat 依赖 (pip install uiautomation pyperclip)\n"
                        "3. 微信客户端未打开"
                    )
                )

        if not req.to:
            return SendResponse(success=False, error="发送目标不能为空")

        if not req.content:
            return SendResponse(success=False, error="消息内容不能为空")

        try:
            # 在线程池中运行 UI 自动化（它是同步阻塞的）
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._send_sync, req)
            return result
        except Exception as e:
            logger.error(f"发送异常: {e}")
            return SendResponse(success=False, error=str(e))

    def _send_sync(self, req: SendRequest) -> SendResponse:
        """同步发送消息（在线程池中执行）"""
        try:
            logger.info(f"[easyChat] 搜索联系人: {req.to}")
            success = self._wechat.send_msg(
                name=req.to,
                at_names=req.at,
                text=req.content,
                search_user=True,
            )
            if success:
                return SendResponse(success=True, message=f"发送成功 → {req.to}")
            else:
                return SendResponse(
                    success=False,
                    error=(
                        f"发送可能失败（未检测到已发送消息）。"
                        f"请检查：\n"
                        f"1. '{req.to}' 是否是正确的联系人/群聊名称\n"
                        f"2. 微信窗口是否在前台\n"
                        f"3. 网络是否正常"
                    )
                )
        except Exception as e:
            return SendResponse(success=False, error=f"发送异常: {e}")

    async def send_file(self, to: str, file_path: str) -> SendResponse:
        """通过 UI 自动化发送文件

        Args:
            to: 联系人/群聊的显示名称
            file_path: 文件本地路径
        """
        if not self._available:
            if not await self.initialize():
                return SendResponse(success=False, error="easyChat 不可用")

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._wechat.send_file(to, file_path, search_user=True)
            )
            return SendResponse(success=True, message=f"文件发送成功 → {to}")
        except Exception as e:
            return SendResponse(success=False, error=str(e))

    @property
    def available(self) -> bool:
        return self._available


class WeFlowSendClient:
    """通过 WeFlow API 发送消息的回退方案

    注意：WeFlow 目前是只读的，不支持发送。
    这里预留接口，等 WeFlow 后续版本支持发送。
    """

    def __init__(self, weflow_client):
        self.weflow = weflow_client

    async def send_message(self, req: SendRequest) -> SendResponse:
        return SendResponse(
            success=False,
            error="WeFlow 目前仅支持读取消息。发送消息需要 easyChat (Windows) 或其他发送渠道。"
        )
