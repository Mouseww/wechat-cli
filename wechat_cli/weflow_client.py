"""WeFlow HTTP API 客户端 - 读取微信消息、联系人、会话"""
from __future__ import annotations
import httpx
import json
import asyncio
from typing import Optional, List, Callable, Dict
from datetime import datetime
from .models import WeChatMessage, SessionType, MessageType
import logging

logger = logging.getLogger("wechat-cli.weflow")


class NameResolver:
    """session_id → 显示名称 的映射管理器

    easyChat 发消息需要用显示名称搜索，不是 wxid。
    从两个来源获取映射：
    1. WeFlow sessions API 启动时预加载
    2. SSE 消息流中实时更新
    """

    def __init__(self):
        # wxid/chatroom_id → display_name
        self._id_to_name: Dict[str, str] = {}
        # display_name → wxid/chatroom_id (反向)
        self._name_to_id: Dict[str, str] = {}

    def update(self, session_id: str, display_name: str):
        """更新映射"""
        if session_id and display_name:
            self._id_to_name[session_id] = display_name
            self._name_to_id[display_name] = session_id

    def get_name(self, session_id: str) -> str:
        """通过 session_id 获取显示名称"""
        return self._id_to_name.get(session_id, "")

    def get_id(self, display_name: str) -> str:
        """通过显示名称获取 session_id"""
        return self._name_to_id.get(display_name, "")

    def resolve(self, key: str) -> str:
        """智能解析：如果 key 是 wxid，返回对应的显示名称；
        如果是显示名称，直接返回"""
        # 先试 id→name
        name = self._id_to_name.get(key)
        if name:
            return name
        # 再看 name→id 存在（说明 key 本身就是名称）
        if key in self._name_to_id:
            return key
        # 都找不到，原样返回
        return key

    @property
    def count(self) -> int:
        return len(self._id_to_name)


class WeFlowClient:
    """WeFlow HTTP API 客户端"""

    def __init__(self, base_url: str = "http://127.0.0.1:5031", token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self._headers = {}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        self.name_resolver = NameResolver()

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        headers = {**self._headers, **kwargs.pop("headers", {})}
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            resp = await client.request(method, url, headers=headers, **kwargs)
            resp.raise_for_status()
            return resp.json()

    # ── 健康检查 ──────────────────────────────────────────────
    async def health(self) -> bool:
        try:
            data = await self._request("GET", "/health")
            return data.get("status") == "ok"
        except Exception:
            return False

    # ── 会话列表 ──────────────────────────────────────────────
    async def get_sessions(self, keyword: Optional[str] = None, limit: int = 100) -> List[dict]:
        params = {"limit": limit}
        if keyword:
            params["keyword"] = keyword
        data = await self._request("GET", "/api/v1/sessions", params=params)
        return data.get("sessions", [])

    # ── 预加载会话名称映射 ──────────────────────────────────────────────
    async def preload_names(self):
        """启动时加载所有会话的 显示名称 ↔ session_id 映射"""
        try:
            sessions = await self.get_sessions(limit=10000)
            for s in sessions:
                sid = s.get("username", "")
                name = s.get("displayName", "")
                if sid and name:
                    self.name_resolver.update(sid, name)
            logger.info(f"预加载 {self.name_resolver.count} 个会话名称映射")
        except Exception as e:
            logger.warning(f"预加载会话名称失败: {e}")

    # ── 联系人列表 ──────────────────────────────────────────────
    async def get_contacts(self, keyword: Optional[str] = None, limit: int = 100) -> List[dict]:
        params = {"limit": limit}
        if keyword:
            params["keyword"] = keyword
        data = await self._request("GET", "/api/v1/contacts", params=params)
        return data.get("contacts", [])

    # ── 获取消息 ──────────────────────────────────────────────
    async def get_messages(
        self,
        talker: str,
        limit: int = 50,
        offset: int = 0,
        start: Optional[str] = None,
        end: Optional[str] = None,
        keyword: Optional[str] = None,
        media: bool = False,
    ) -> dict:
        params = {"talker": talker, "limit": limit, "offset": offset}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        if keyword:
            params["keyword"] = keyword
        if media:
            params["media"] = "1"
        return await self._request("GET", "/api/v1/messages", params=params)

    # ── 群成员 ──────────────────────────────────────────────
    async def get_group_members(self, chatroom_id: str) -> dict:
        params = {"chatroomId": chatroom_id}
        return await self._request("GET", "/api/v1/group-members", params=params)

    # ── SSE 新消息推送 ──────────────────────────────────────────────
    async def subscribe_messages(self, on_message: Callable[[WeChatMessage], None]) -> None:
        """订阅 WeFlow SSE 新消息推送，收到消息时调用回调"""
        url = f"{self.base_url}/api/v1/push/messages"
        params = {}
        if self.token:
            params["access_token"] = self.token

        logger.info(f"连接 WeFlow SSE: {url}")
        while True:
            try:
                async with httpx.AsyncClient(timeout=None, trust_env=False) as client:
                    async with client.stream("GET", url, params=params, headers=self._headers) as resp:
                        resp.raise_for_status()
                        event_type = None
                        async for line in resp.aiter_lines():
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("event:"):
                                event_type = line[6:].strip()
                            elif line.startswith("data:") and event_type:
                                data_str = line[5:].strip()
                                try:
                                    data = json.loads(data_str)
                                    msg = self._parse_sse_message(data)
                                    if msg:
                                        asyncio.create_task(self._safe_callback(on_message, msg))
                                except json.JSONDecodeError:
                                    pass
                                event_type = None
            except (httpx.ConnectError, httpx.ReadTimeout) as e:
                logger.warning(f"SSE 连接断开: {e}，5秒后重试...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"SSE 错误: {e}，5秒后重试...")
                await asyncio.sleep(5)

    async def _safe_callback(self, callback, msg):
        try:
            result = callback(msg)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"消息回调出错: {e}")

    def _parse_sse_message(self, data: dict) -> Optional[WeChatMessage]:
        """解析 WeFlow SSE 推送的消息

        WeFlow SSE data 字段:
        - event: "message.new"
        - sessionId: wxid_xxx 或 xxx@chatroom
        - sessionType: "private" 或 "group"
        - sourceName: 发送者显示名称
        - groupName: 群聊名称 (仅群聊)
        - content: 消息内容
        - rawid: 消息唯一ID
        - timestamp: Unix时间戳
        """
        event = data.get("event", "")
        if event not in ("message.new",):
            return None

        session_id = data.get("sessionId", "")
        session_type_str = data.get("sessionType", "other")
        session_type = {
            "group": SessionType.GROUP,
            "private": SessionType.PRIVATE,
        }.get(session_type_str, SessionType.OTHER)

        source_name = data.get("sourceName", "")
        group_name = data.get("groupName") if session_type == SessionType.GROUP else None

        # 确定会话显示名称
        # - 私聊: sourceName 就是对方的显示名称
        # - 群聊: groupName 是群的显示名称
        if session_type == SessionType.PRIVATE:
            session_name = source_name
        elif session_type == SessionType.GROUP:
            session_name = group_name or ""
        else:
            session_name = source_name

        # 更新名称映射
        if session_id and session_name:
            self.name_resolver.update(session_id, session_name)

        content = data.get("content", "")
        # 判断消息类型
        msg_type = MessageType.TEXT
        if content == "[图片]":
            msg_type = MessageType.IMAGE
        elif content == "[语音]":
            msg_type = MessageType.VOICE
        elif content == "[视频]":
            msg_type = MessageType.VIDEO
        elif content.startswith("[文件]"):
            msg_type = MessageType.FILE
        elif content.startswith("[动画表情]"):
            msg_type = MessageType.EMOJI

        return WeChatMessage(
            session_id=session_id,
            session_name=session_name,
            session_type=session_type,
            sender_id="",
            sender_name=source_name,
            group_name=group_name,
            content=content,
            message_type=msg_type,
            timestamp=data.get("timestamp", 0),
            message_id=str(data.get("rawid", "")),
            is_self=False,
        )

    def _parse_weflow_message(self, msg: dict, session_id: str, session_type: SessionType) -> WeChatMessage:
        """解析 WeFlow API 返回的消息"""
        content = msg.get("content", "")
        parsed = msg.get("parsedContent", content)
        media_type = msg.get("mediaType", "")
        media_url = msg.get("mediaUrl", "")

        msg_type = MessageType.TEXT
        if media_type == "image":
            msg_type = MessageType.IMAGE
        elif media_type == "voice":
            msg_type = MessageType.VOICE
        elif media_type == "video":
            msg_type = MessageType.VIDEO
        elif media_type == "emoji":
            msg_type = MessageType.EMOJI

        return WeChatMessage(
            session_id=session_id,
            session_name=self.name_resolver.get_name(session_id),
            session_type=session_type,
            sender_id=msg.get("senderUsername", ""),
            sender_name="",
            content=parsed or content,
            raw_content=msg.get("rawContent"),
            message_type=msg_type,
            timestamp=msg.get("createTime", 0),
            message_id=str(msg.get("serverId", msg.get("localId", ""))),
            is_self=bool(msg.get("isSend", 0)),
            media_url=media_url,
        )
