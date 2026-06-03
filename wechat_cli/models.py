"""数据模型定义"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


class SessionType(str, Enum):
    PRIVATE = "private"
    GROUP = "group"
    OTHER = "other"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    EMOJI = "emoji"
    LINK = "link"
    SYSTEM = "system"
    UNKNOWN = "unknown"


class WeChatMessage(BaseModel):
    """微信消息"""
    session_id: str = Field(..., description="会话ID (wxid 或 xxx@chatroom)")
    session_name: str = Field(default="", description="会话显示名称（用于搜索定位）")
    session_type: SessionType = Field(default=SessionType.OTHER)
    sender_id: str = Field(default="", description="发送者 wxid")
    sender_name: str = Field(default="", description="发送者昵称/备注")
    group_name: Optional[str] = Field(default=None, description="群聊名称")
    content: str = Field(default="", description="消息文本内容")
    raw_content: Optional[str] = Field(default=None, description="原始消息内容")
    message_type: MessageType = Field(default=MessageType.TEXT)
    timestamp: int = Field(default=0, description="Unix 时间戳")
    message_id: str = Field(default="", description="消息唯一ID")
    is_self: bool = Field(default=False, description="是否自己发送的")
    media_url: Optional[str] = Field(default=None, description="媒体URL")

    @property
    def is_group(self) -> bool:
        return self.session_type == SessionType.GROUP

    @property
    def display_time(self) -> str:
        if self.timestamp:
            return datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        return "unknown"

    @property
    def reply_target(self) -> str:
        """用于 easyChat 搜索的回复目标名称

        - 私聊: 对方的显示名称 (session_name)
        - 群聊: 群聊名称 (group_name 或 session_name)
        """
        if self.is_group:
            return self.group_name or self.session_name
        return self.session_name or self.sender_name


class SendRequest(BaseModel):
    """发送消息请求"""
    to: str = Field(..., description="接收者显示名称（不是wxid，是微信里搜得到的名称）")
    content: str = Field(..., description="消息内容")
    at: Optional[List[str]] = Field(default=None, description="@的用户列表")
    message_type: MessageType = Field(default=MessageType.TEXT)


class SendResponse(BaseModel):
    """发送消息响应"""
    success: bool
    message: str = ""
    error: Optional[str] = None


class AgentRequest(BaseModel):
    """发给 AI Agent 的请求"""
    message: WeChatMessage
    history: Optional[List[WeChatMessage]] = Field(default=None, description="最近消息历史")
    context: Optional[dict] = Field(default=None, description="额外上下文")


class AgentResponse(BaseModel):
    """AI Agent 返回的响应

    reply: 回复文本内容
    action: reply=回复, skip=跳过, forward=转发
    reply_to: 可选，指定回复到哪个会话（覆盖默认的原会话回复）
    """
    reply: Optional[str] = Field(default=None, description="回复文本")
    action: str = Field(default="reply", description="动作: reply/skip/forward")
    reply_to: Optional[str] = Field(default=None, description="回复目标名称（覆盖默认）")
    target: Optional[str] = Field(default=None, description="转发目标名称")
    metadata: Optional[dict] = Field(default=None)


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "127.0.0.1"
    port: int = 5032
    weflow_url: str = "http://127.0.0.1:5031"
    weflow_token: Optional[str] = None
    agent_webhook: Optional[str] = Field(default=None, description="AI Agent 回调 URL")
    agent_api_key: Optional[str] = Field(default=None)
    auto_reply_enabled: bool = False
    log_level: str = "INFO"
    reply_delay_ms: int = 500
    read_driver: str = "weflow"
    send_driver: str = "native"
    # 兼容旧配置；新配置请使用 read_driver / send_driver。
    use_native_driver: bool = False
    wechat_data_path: Optional[str] = None # 自动检测
    wechat_hotkey: str = "{Ctrl}{Alt}w"
    # 过滤规则
    listen_sessions: Optional[List[str]] = Field(default=None, description="监听的会话白名单（填wxid或显示名称均可）")
    ignore_sessions: Optional[List[str]] = Field(default=None, description="忽略的会话黑名单")
    listen_keywords: Optional[List[str]] = Field(default=None, description="监听的关键词")

    @property
    def effective_read_driver(self) -> str:
        """返回实际读取通道。"""
        return "native" if self.use_native_driver else self.read_driver

    @property
    def effective_send_driver(self) -> str:
        """返回实际发送通道。"""
        return "native" if self.use_native_driver else self.send_driver
