"""HTTP API 服务器 - 为第三方工具提供统一接口

API 端点：
- GET  /health                    健康检查
- GET  /api/v1/sessions           获取会话列表
- GET  /api/v1/contacts           获取联系人列表
- GET  /api/v1/messages           获取消息历史
- POST /api/v1/send               发送消息
- POST /api/v1/agent/callback     Agent 回调端点（接收 Agent 主动回复）
- GET  /api/v1/stream/messages    SSE 消息流（转发给第三方）
- GET  /api/v1/stats              统计信息
- POST /api/v1/config             更新配置
"""
from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional, Set
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from .models import (
    ServerConfig, SendRequest, SendResponse,
    WeChatMessage, AgentResponse, MessageType,
)
from .weflow_client import WeFlowClient
from .easychat_client import EasyChatClient
from .agent_bridge import AgentBridge

logger = logging.getLogger("wechat-cli.server")


class SSEManager:
    """SSE 连接管理器"""
    def __init__(self):
        self._queues: dict[str, asyncio.Queue] = {}

    def subscribe(self, client_id: str) -> asyncio.Queue:
        q = asyncio.Queue(maxsize=100)
        self._queues[client_id] = q
        return q

    def unsubscribe(self, client_id: str):
        self._queues.pop(client_id, None)

    async def broadcast(self, event: str, data: dict):
        dead = []
        for cid, q in self._queues.items():
            try:
                q.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:
                dead.append(cid)
        for cid in dead:
            self._queues.pop(cid, None)


def create_app(config: ServerConfig) -> FastAPI:
    """创建 FastAPI 应用"""

    bridge = AgentBridge(config)
    sse_manager = SSEManager()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 启动时初始化
        logger.info("正在初始化 WeChat CLI 服务...")
        # 将 bridge 挂到 app 上方便引用
        app.state.bridge = bridge
        yield
        # 关闭时清理
        await bridge.stop()

    app = FastAPI(
        title="WeChat CLI API",
        description="第三方工具对接微信的统一桥梁 (WeFlow + easyChat)",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── 依赖注入 ──────────────────────────────────────────────
    def get_bridge() -> AgentBridge:
        return bridge

    def get_weflow() -> WeFlowClient:
        return bridge.weflow

    # ── 健康检查 ──────────────────────────────────────────────
    @app.get("/health")
    async def health():
        weflow_ok = await bridge.weflow.health()
        return {
            "status": "ok" if weflow_ok else "degraded",
            "weflow": "connected" if weflow_ok else "disconnected",
            "easychat": "available" if bridge.easychat.available else "unavailable",
        }

    # ── 会话列表 ──────────────────────────────────────────────
    @app.get("/api/v1/sessions")
    async def get_sessions(
        keyword: Optional[str] = None,
        limit: int = Query(default=100, le=1000),
        wf: WeFlowClient = Depends(get_weflow),
    ):
        try:
            sessions = await wf.get_sessions(keyword=keyword, limit=limit)
            return {"success": True, "count": len(sessions), "sessions": sessions}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"WeFlow 请求失败: {e}")

    # ── 联系人列表 ──────────────────────────────────────────────
    @app.get("/api/v1/contacts")
    async def get_contacts(
        keyword: Optional[str] = None,
        limit: int = Query(default=100, le=1000),
        wf: WeFlowClient = Depends(get_weflow),
    ):
        try:
            contacts = await wf.get_contacts(keyword=keyword, limit=limit)
            return {"success": True, "count": len(contacts), "contacts": contacts}
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"WeFlow 请求失败: {e}")

    # ── 消息历史 ──────────────────────────────────────────────
    @app.get("/api/v1/messages")
    async def get_messages(
        talker: str = Query(..., description="会话 ID"),
        limit: int = Query(default=50, le=10000),
        offset: int = Query(default=0, ge=0),
        start: Optional[str] = None,
        end: Optional[str] = None,
        keyword: Optional[str] = None,
        media: bool = False,
        wf: WeFlowClient = Depends(get_weflow),
    ):
        try:
            data = await wf.get_messages(
                talker=talker, limit=limit, offset=offset,
                start=start, end=end, keyword=keyword, media=media,
            )
            return data
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"WeFlow 请求失败: {e}")

    # ── 发送消息 ──────────────────────────────────────────────
    @app.post("/api/v1/send", response_model=SendResponse)
    async def send_message(
        req: SendRequest,
        br: AgentBridge = Depends(get_bridge),
    ):
        result = await br.send(req)
        if not result.success:
            raise HTTPException(status_code=502, detail=result.error)
        return result

    # ── Agent 回调 ──────────────────────────────────────────────
    @app.post("/api/v1/agent/callback")
    async def agent_callback(
        request: Request,
        br: AgentBridge = Depends(get_bridge),
    ):
        """供 AI Agent 主动调用的回调端点

        Agent 可以通过此端点主动发送消息到微信：
        POST /api/v1/agent/callback
        {
            "to": "张三 或 群聊名称（显示名称，不是wxid）",
            "content": "回复内容",
            "action": "reply"
        }
        """
        data = await request.json()
        to = data.get("to") or data.get("session_id") or data.get("session_name")
        content = data.get("content") or data.get("reply")
        action = data.get("action", "reply")

        if not to or not content:
            raise HTTPException(status_code=400, detail="缺少 to 或 content")

        if action == "reply":
            # ★ 智能解析：如果传入的是 wxid，自动转换为显示名称
            resolver = br.weflow.name_resolver
            to_name = resolver.resolve(to)
            if to_name != to:
                logger.info(f"名称解析: {to} → {to_name}")

            req = SendRequest(to=to_name, content=content)
            result = await br.send(req)
            return {"success": result.success, "error": result.error}
        else:
            return {"success": True, "action": action}

    # ── SSE 消息流 ──────────────────────────────────────────────
    @app.get("/api/v1/stream/messages")
    async def stream_messages(request: Request):
        """SSE 端点 - 实时推送新消息给第三方工具

        连接方式：
        curl -N http://localhost:5032/api/v1/stream/messages
        """
        import uuid
        client_id = str(uuid.uuid4())
        queue = sse_manager.subscribe(client_id)

        # 注册桥接器回调，将消息同时推送到 SSE
        original_callback = bridge.weflow._safe_callback

        async def sse_broadcast(msg: WeChatMessage):
            await sse_manager.broadcast("message.new", msg.model_dump())

        try:
            # 临时添加 SSE 广播回调
            async def on_msg(msg: WeChatMessage):
                await bridge._on_new_message(msg)
                await sse_broadcast(msg)

            async def event_generator():
                try:
                    while True:
                        if await request.is_disconnected():
                            break
                        try:
                            item = await asyncio.wait_for(queue.get(), timeout=30)
                            yield {
                                "event": item["event"],
                                "data": json.dumps(item["data"], ensure_ascii=False),
                            }
                        except asyncio.TimeoutError:
                            yield {"event": "heartbeat", "data": "{}"}
                finally:
                    sse_manager.unsubscribe(client_id)

            return EventSourceResponse(event_generator())
        except Exception:
            sse_manager.unsubscribe(client_id)
            raise

    # ── 统计信息 ──────────────────────────────────────────────
    @app.get("/api/v1/stats")
    async def get_stats(br: AgentBridge = Depends(get_bridge)):
        return br.get_stats()

    # ── 动态配置 ──────────────────────────────────────────────
    @app.post("/api/v1/config")
    async def update_config(request: Request, br: AgentBridge = Depends(get_bridge)):
        """运行时更新配置"""
        data = await request.json()
        updated = []
        if "auto_reply_enabled" in data:
            br.config.auto_reply_enabled = bool(data["auto_reply_enabled"])
            updated.append("auto_reply_enabled")
        if "agent_webhook" in data:
            br.config.agent_webhook = data["agent_webhook"]
            updated.append("agent_webhook")
        if "listen_sessions" in data:
            br.config.listen_sessions = data["listen_sessions"]
            updated.append("listen_sessions")
        if "ignore_sessions" in data:
            br.config.ignore_sessions = data["ignore_sessions"]
            updated.append("ignore_sessions")
        if "listen_keywords" in data:
            br.config.listen_keywords = data["listen_keywords"]
            updated.append("listen_keywords")
        if "reply_delay_ms" in data:
            br.config.reply_delay_ms = int(data["reply_delay_ms"])
            updated.append("reply_delay_ms")
        return {"success": True, "updated": updated}

    return app
