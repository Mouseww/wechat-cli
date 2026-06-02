"""Agent Bridge - 连接微信消息与 AI Agent

核心流程：
1. WeFlow SSE 推送新消息（含 sessionId + 显示名称）
2. 过滤后转发给 AI Agent webhook
3. Agent 返回回复文本
4. 通过 easyChat UI 自动化发送回复到正确的会话

关键点：easyChat 发消息需要搜索显示名称，不是 wxid。
所以必须维护 session_id → 显示名称 的映射。
"""
from __future__ import annotations
import asyncio
import httpx
import json
import time
import logging
import re
from typing import Optional, List, Dict, Deque
from collections import deque, defaultdict
from .models import (
    WeChatMessage, AgentRequest, AgentResponse,
    SendRequest, MessageType, SessionType, ServerConfig,
    SendResponse,
)
from .weflow_client import WeFlowClient
from .easychat_client import EasyChatClient
from .native_ui import native_send_handler
from .db_reader import WeChatDBReader
from .key_extractor import get_key

logger = logging.getLogger("wechat-cli.bridge")


class MessageBuffer:
    """消息历史缓冲区 - 按会话存储最近的消息"""

    def __init__(self, max_per_session: int = 50):
        self.max_per_session = max_per_session
        self._buffers: Dict[str, Deque[WeChatMessage]] = defaultdict(
            lambda: deque(maxlen=max_per_session)
        )

    def add(self, msg: WeChatMessage):
        self._buffers[msg.session_id].append(msg)

    def get_history(self, session_id: str, limit: int = 10) -> List[WeChatMessage]:
        buf = self._buffers.get(session_id, deque())
        return list(buf)[-limit:]

    def clear(self, session_id: Optional[str] = None):
        if session_id:
            self._buffers.pop(session_id, None)
        else:
            self._buffers.clear()


class AgentBridge:
    """Agent 桥接器 - 微信消息 ↔ AI Agent"""

    def __init__(self, config: ServerConfig):
        self.config = config
        self.weflow = WeFlowClient(config.weflow_url, config.weflow_token)
        self.easychat = EasyChatClient()
        self.db_reader = None
        self.msg_buffer = MessageBuffer()
        self._running = False
        self._stats = {
            "messages_received": 0,
            "messages_forwarded": 0,
            "replies_sent": 0,
            "errors": 0,
            "started_at": None,
        }
        # 去重
        self._seen_ids: Deque[str] = deque(maxlen=1000)
        # 速率限制：同一会话短时间内不重复触发
        self._last_trigger: Dict[str, float] = {}
        self._min_interval = 1.0  # 同一会话最小触发间隔（秒）
        self._native_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动桥接器"""
        self._running = True
        self._stats["started_at"] = time.time()
        read_driver = self.config.effective_read_driver
        send_driver = self.config.effective_send_driver
        logger.info("Agent Bridge 启动中...")

        if read_driver == "weflow":
            healthy = await self.weflow.health()
            if not healthy:
                logger.error("无法连接 WeFlow，请确保 WeFlow 已启动且 API 服务已开启")
                raise ConnectionError("WeFlow 连接失败")
            logger.info(f"✓ WeFlow 连接成功 ({self.config.weflow_url})")
        else:
            logger.info("✓ 读取通道使用原生数据库轮询")

        if send_driver == "native":
            logger.info("✓ 原生 UI 发送通道使用内置驱动")
        else:
            # ★ 预加载会话名称映射（wxid → 显示名称）
            await self.weflow.preload_names()

            # 初始化 easyChat
            await self.easychat.initialize()
            if self.easychat.available:
                logger.info("✓ easyChat 发送通道就绪")
            else:
                logger.warning("⚠ easyChat 不可用，只能读取消息，无法发送回复")

        # 启动 SSE 订阅
        logger.info("开始监听新消息...")
        if read_driver == "native":
            self._native_task = asyncio.create_task(self._start_native_polling())
        else:
            await self.weflow.subscribe_messages(self._on_new_message)

    async def _start_native_polling(self):
        """后台启动原生数据库轮询；微信未就绪时定时重试。"""
        while self._running:
            try:
                key = await asyncio.wait_for(asyncio.to_thread(get_key), timeout=10)
            except asyncio.TimeoutError:
                logger.warning("提取微信数据库 Key 超时，30 秒后重试")
                await asyncio.sleep(30)
                continue
            if not key or not re.fullmatch(r"[0-9a-fA-F]{64}", key):
                logger.warning("未能提取有效的微信数据库 Key，30 秒后重试")
                await asyncio.sleep(30)
                continue
            self.db_reader = WeChatDBReader(
                key=key,
                db_path=self.config.wechat_data_path,
            )
            await self.db_reader.start_polling(self._on_new_message)
            return

    async def stop(self):
        self._running = False
        if self._native_task and not self._native_task.done():
            self._native_task.cancel()
            try:
                await self._native_task
            except asyncio.CancelledError:
                pass
        logger.info("Agent Bridge 已停止")

    def get_stats(self) -> dict:
        stats = dict(self._stats)
        stats["buffer_size"] = sum(len(b) for b in self.msg_buffer._buffers.values())
        stats["name_cache_size"] = self.weflow.name_resolver.count
        stats["uptime"] = time.time() - stats["started_at"] if stats["started_at"] else 0
        return stats

    # ── 消息过滤 ──────────────────────────────────────────────
    def _should_process(self, msg: WeChatMessage) -> bool:
        """判断消息是否需要处理"""
        # 忽略自己发的消息
        if msg.is_self:
            return False

        # 白名单过滤（支持 wxid 和显示名称）
        if self.config.listen_sessions:
            allowed = False
            for s in self.config.listen_sessions:
                if s == msg.session_id or s == msg.session_name or s == msg.reply_target:
                    allowed = True
                    break
            if not allowed:
                return False

        # 黑名单过滤（支持 wxid 和显示名称）
        if self.config.ignore_sessions:
            for s in self.config.ignore_sessions:
                if s == msg.session_id or s == msg.session_name or s == msg.reply_target:
                    return False

        # 关键词过滤
        if self.config.listen_keywords:
            if not any(kw in msg.content for kw in self.config.listen_keywords):
                return False

        # 去重
        if msg.message_id in self._seen_ids:
            return False
        self._seen_ids.append(msg.message_id)

        # 速率限制
        now = time.time()
        last = self._last_trigger.get(msg.session_id, 0)
        if now - last < self._min_interval:
            return False
        self._last_trigger[msg.session_id] = now

        return True

    # ── 新消息处理 ──────────────────────────────────────────────
    async def _on_new_message(self, msg: WeChatMessage):
        """处理收到的新消息"""
        self._stats["messages_received"] += 1
        self.msg_buffer.add(msg)

        if not self._should_process(msg):
            return

        if not self.config.auto_reply_enabled:
            logger.debug(f"自动回复已关闭，跳过: {msg.sender_name}: {msg.content[:50]}")
            return

        # 日志：显示会话名称和发送者
        target_display = msg.reply_target
        if msg.is_group:
            logger.info(f"新消息 [群:{target_display}] {msg.sender_name}: {msg.content[:100]}")
        else:
            logger.info(f"新消息 [私聊:{target_display}] {msg.content[:100]}")

        # 如果配置了 Agent Webhook，转发给 Agent
        if self.config.agent_webhook:
            try:
                await self._forward_to_agent(msg)
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"转发给 Agent 失败: {e}")

    # ── Agent 转发 ──────────────────────────────────────────────
    async def _forward_to_agent(self, msg: WeChatMessage):
        """将消息转发给 AI Agent，并处理回复"""
        self._stats["messages_forwarded"] += 1

        # 构建请求，附带上下文
        history = self.msg_buffer.get_history(msg.session_id, limit=10)
        agent_req = AgentRequest(
            message=msg,
            history=history,
            context={
                "session_type": msg.session_type.value,
                "is_group": msg.is_group,
                "session_id": msg.session_id,
                "session_name": msg.session_name,
                "group_name": msg.group_name,
                "sender_name": msg.sender_name,
                "reply_target": msg.reply_target,
            },
        )

        # 发送到 Agent Webhook
        headers = {"Content-Type": "application/json"}
        if self.config.agent_api_key:
            headers["Authorization"] = f"Bearer {self.config.agent_api_key}"

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self.config.agent_webhook,
                json=agent_req.model_dump(),
                headers=headers,
            )
            resp.raise_for_status()

        # 解析 Agent 响应
        data = resp.json()
        agent_resp = AgentResponse(**data)

        if agent_resp.action == "reply" and agent_resp.reply:
            # 延迟发送回复（模拟人类）
            if self.config.reply_delay_ms > 0:
                await asyncio.sleep(self.config.reply_delay_ms / 1000)

            # ★ 确定回复目标名称
            # 优先用 Agent 指定的 reply_to，否则用消息的 reply_target
            reply_to = agent_resp.reply_to or msg.reply_target

            if not reply_to:
                logger.error(f"无法确定回复目标！session_id={msg.session_id}, session_name={msg.session_name}")
                self._stats["errors"] += 1
                return

            logger.info(f"发送回复 → [{reply_to}]: {agent_resp.reply[:80]}")

            send_req = SendRequest(
                to=reply_to,
                content=agent_resp.reply,
            )
            result = await self.send(send_req)
            if result.success:
                self._stats["replies_sent"] += 1
                logger.info(f"✓ 回复已发送到 [{reply_to}]")
            else:
                self._stats["errors"] += 1
                logger.error(f"✗ 回复发送失败 [{reply_to}]: {result.error}")

        elif agent_resp.action == "skip":
            logger.debug("Agent 选择跳过此消息")
        elif agent_resp.action == "forward" and agent_resp.target:
            # 转发消息到指定目标
            logger.info(f"Agent 要求转发到: {agent_resp.target}")
            if agent_resp.reply:
                send_req = SendRequest(to=agent_resp.target, content=agent_resp.reply)
                result = await self.send(send_req)
                if result.success:
                    logger.info(f"✓ 转发成功到 [{agent_resp.target}]")
                else:
                    logger.error(f"✗ 转发失败: {result.error}")

    # ── 手动发送 ──────────────────────────────────────────────
    async def send(self, req: SendRequest):
        """手动发送消息

        req.to 应该是显示名称（微信里搜得到的名称）
        """
        if self.config.effective_send_driver == "native":
            success = await native_send_handler(req.to, req.content)
            return SendResponse(
                success=success, 
                message="发送成功" if success else "发送失败",
                error=None if success else "原生 UI 驱动发送失败"
            )
        return await self.easychat.send_message(req)
