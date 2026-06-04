"""WeChat CLI WebUI - 独立的 Web 配置管理界面"""
from __future__ import annotations
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from .config import load_config, save_config, get_config_path
from .models import ServerConfig

logger = logging.getLogger(__name__)


class ConfigUpdate(BaseModel):
    """配置更新请求"""
    host: Optional[str] = None
    port: Optional[int] = None
    weflow_url: Optional[str] = None
    weflow_token: Optional[str] = None
    agent_webhook: Optional[str] = None
    agent_api_key: Optional[str] = None
    auto_reply_enabled: Optional[bool] = None
    log_level: Optional[str] = None
    reply_delay_ms: Optional[int] = None
    read_driver: Optional[str] = None
    send_driver: Optional[str] = None
    use_native_driver: Optional[bool] = None
    wechat_data_path: Optional[str] = None
    wechat_hotkey: Optional[str] = None
    listen_sessions: Optional[list] = None
    ignore_sessions: Optional[list] = None
    listen_keywords: Optional[list] = None
    # Agent 提示词
    agent_system_prompt: Optional[str] = None
    agent_group_prompt: Optional[str] = None
    agent_model: Optional[str] = None
    agent_base_url: Optional[str] = None
    agent_temperature: Optional[float] = None
    agent_max_tokens: Optional[int] = None
    agent_max_history: Optional[int] = None


def create_webui_app() -> FastAPI:
    """创建 WebUI FastAPI 应用"""
    app = FastAPI(title="WeChat CLI WebUI", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """返回 WebUI 主页面"""
        html_path = Path(__file__).parent / "webui_assets" / "index.html"
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    @app.get("/api/config")
    async def get_config():
        """获取当前配置"""
        config = load_config()
        data = config.model_dump()
        # 敏感字段脱敏
        safe_data = {**data}
        if safe_data.get("weflow_token"):
            safe_data["_weflow_token_set"] = True
        if safe_data.get("agent_api_key"):
            safe_data["_agent_api_key_set"] = True
        safe_data["_config_path"] = str(get_config_path())
        return JSONResponse(content=safe_data)

    @app.put("/api/config")
    async def update_config(update: ConfigUpdate):
        """更新配置"""
        config = load_config()
        update_data = update.model_dump(exclude_none=True)

        for key, value in update_data.items():
            if hasattr(config, key):
                setattr(config, key, value)

        save_config(config)
        return JSONResponse(content={"success": True, "message": "配置已保存"})

    @app.post("/api/config/reset")
    async def reset_config():
        """重置配置为默认值"""
        config = ServerConfig()
        save_config(config)
        return JSONResponse(content={"success": True, "message": "配置已重置为默认值"})

    @app.get("/api/status")
    async def get_status():
        """获取服务状态"""
        config = load_config()
        status = {
            "config_path": str(get_config_path()),
            "config_exists": get_config_path().exists(),
            "effective_read_driver": config.effective_read_driver,
            "effective_send_driver": config.effective_send_driver,
        }

        # 检查 WeFlow 连接
        if config.effective_read_driver == "weflow":
            try:
                from .weflow_client import WeFlowClient
                wf = WeFlowClient(config.weflow_url, config.weflow_token)
                status["weflow_connected"] = await wf.health()
            except Exception:
                status["weflow_connected"] = False
        else:
            status["weflow_connected"] = None

        # 检查原生驱动
        try:
            from .diagnostics import get_native_driver_status
            native = get_native_driver_status(config.wechat_data_path)
            status["wechat_running"] = native.get("wechat_running", False)
            status["native_read_ready"] = native.get("read_ready", False)
            status["native_send_ready"] = native.get("send_ready", False)
            status["db_path"] = native.get("db_path")
            status["db_format"] = native.get("db_format", "unknown")
            status["platform"] = native.get("platform", "unknown")
        except Exception:
            status["wechat_running"] = False
            status["native_read_ready"] = False
            status["native_send_ready"] = False

        # 检查 Agent 连接
        if config.agent_webhook:
            try:
                import httpx
                headers = {"Content-Type": "application/json"}
                if config.agent_api_key:
                    headers["Authorization"] = f"Bearer {config.agent_api_key}"
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.post(
                        config.agent_webhook,
                        json={
                            "message": {
                                "session_id": "healthcheck",
                                "session_type": "private",
                                "sender_name": "WebUI",
                                "content": "ping",
                                "message_type": "text",
                                "timestamp": 0,
                                "message_id": "webui-healthcheck",
                                "is_self": False,
                            },
                            "history": [],
                        },
                        headers=headers,
                    )
                    status["agent_connected"] = resp.status_code == 200
            except Exception:
                status["agent_connected"] = False
        else:
            status["agent_connected"] = None

        return JSONResponse(content=status)

    @app.post("/api/agent/test")
    async def test_agent():
        """测试 Agent 连通性"""
        config = load_config()
        if not config.agent_webhook:
            raise HTTPException(status_code=400, detail="未设置 Agent Webhook")

        try:
            import httpx
            headers = {"Content-Type": "application/json"}
            if config.agent_api_key:
                headers["Authorization"] = f"Bearer {config.agent_api_key}"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    config.agent_webhook,
                    json={
                        "message": {
                            "session_id": "test",
                            "session_type": "private",
                            "sender_name": "WebUI测试",
                            "content": "你好，这是一条测试消息。",
                            "message_type": "text",
                            "timestamp": 0,
                            "message_id": "webui-test-001",
                            "is_self": False,
                        },
                        "history": [],
                    },
                    headers=headers,
                )
                return JSONResponse(content={
                    "success": resp.status_code == 200,
                    "status_code": resp.status_code,
                    "response": resp.json() if resp.status_code == 200 else resp.text[:500],
                })
        except Exception as e:
            return JSONResponse(content={
                "success": False,
                "error": str(e),
            })

    @app.post("/api/weflow/test")
    async def test_weflow():
        """测试 WeFlow 连接"""
        config = load_config()
        try:
            from .weflow_client import WeFlowClient
            wf = WeFlowClient(config.weflow_url, config.weflow_token)
            healthy = await wf.health()
            result = {"success": healthy, "url": config.weflow_url}
            if healthy:
                sessions = await wf.get_sessions(limit=3)
                result["session_count"] = len(sessions)
            return JSONResponse(content=result)
        except Exception as e:
            return JSONResponse(content={
                "success": False,
                "url": config.weflow_url,
                "error": str(e),
            })

    return app


def run_webui(host: str = "127.0.0.1", port: int = 5033):
    """启动 WebUI 服务"""
    import uvicorn
    app = create_webui_app()
    print(f"\n  🌐 WeChat CLI WebUI 已启动")
    print(f"  👉 打开浏览器访问: http://{host}:{port}")
    print(f"  按 Ctrl+C 停止\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")
