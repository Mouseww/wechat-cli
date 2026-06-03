"""WeChat CLI - 命令行入口

用法：
    wechat-cli start              启动服务
    wechat-cli status             查看状态
    wechat-cli sessions           列出会话
    wechat-cli contacts           列出联系人
    wechat-cli messages <talker>  查看消息
    wechat-cli send <to> <msg>    发送消息
    wechat-cli config show        查看配置
    wechat-cli config set <k> <v> 设置配置
    wechat-cli agent set <url>    设置 Agent Webhook
"""
from __future__ import annotations
import asyncio
import sys
import json
import click
import logging
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint
from .diagnostics import get_native_driver_status


def _configure_stdio_encoding() -> None:
    """确保 Windows GBK 控制台可以输出项目中的 Unicode 文本。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")


_configure_stdio_encoding()
console = Console()


def _load_config():
    from .config import load_config
    return load_config()


def _save_config(config) -> None:
    from .config import save_config
    save_config(config)


def _get_config_path():
    from .config import get_config_path
    return get_config_path()


def _get_send_models():
    from .models import SendRequest, SendResponse
    return SendRequest, SendResponse


def _load_send_config() -> dict:
    """读取 send 命令所需的最小配置，避免加载完整 Pydantic 模型。"""
    data = _load_raw_config()
    return {
        "send_driver": data.get("send_driver", "native"),
        "use_native_driver": bool(data.get("use_native_driver", False)),
    }


def _load_weflow_config() -> dict:
    """读取 WeFlow 命令所需的最小配置，避免加载完整 Pydantic 模型。"""
    data = _load_raw_config()
    return {
        "weflow_url": data.get("weflow_url", "http://127.0.0.1:5031"),
        "weflow_token": data.get("weflow_token"),
    }


def _load_raw_config() -> dict:
    path = Path.home() / ".wechat-cli" / "config.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _weflow_get(path: str, params: dict, config: dict) -> dict:
    base_url = config.get("weflow_url", "http://127.0.0.1:5031").rstrip("/")
    query = urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{query}"

    headers = {}
    token = config.get("weflow_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_weflow_client_class():
    from .weflow_client import WeFlowClient
    return WeFlowClient


def _get_easychat_client_class():
    from .easychat_client import EasyChatClient
    return EasyChatClient


def _get_native_send_handler():
    from .native_ui import native_send_handler
    return native_send_handler


def _ensure_weflow_api(config: dict | object, *, wait_seconds: float = 8.0) -> bool:
    from .weflow_runtime import ensure_weflow_api

    if isinstance(config, dict):
        url = config.get("weflow_url", "http://127.0.0.1:5031")
        token = config.get("weflow_token")
    else:
        url = getattr(config, "weflow_url", "http://127.0.0.1:5031")
        token = getattr(config, "weflow_token", None)

    ok, status = ensure_weflow_api(url, token, wait_seconds=wait_seconds)
    if status.startswith("started:"):
        console.print(f"[green]✓[/green] 已启动 WeFlow，API 已可用 ({url})")
    elif status == "executable-not-found":
        console.print("[yellow]未找到 WeFlow 可执行文件，请先运行 `install.bat` 安装 WeFlow。[/yellow]")
    elif status.startswith("started-but-api-unavailable"):
        console.print("[yellow]已启动 WeFlow，但 API 尚不可用；请确认 WeFlow 已连接微信数据源并启用 API 服务。[/yellow]")
    return ok


def _table_cell(value, default: str = "") -> str:
    """将 API 返回值规范为 Rich 表格可渲染文本。"""
    if value is None:
        return default
    return str(value)


def setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def print_weflow_unavailable_error(error: Exception) -> None:
    """输出 WeFlow 不可用时的用户可读错误。"""
    console.print(f"[red]✗ WeFlow 连接失败:[/red] {error}")
    console.print("  当前命令需要 WeFlow API 提供会话/历史消息查询。")
    console.print("  若使用原生驱动，请先运行 `wechat-cli status` 确认微信进程和数据库已就绪。")


@click.group()
@click.version_option(version="0.1.0", prog_name="wechat-cli")
def cli():
    """🤖 WeChat CLI - 第三方工具对接微信的统一桥梁

    结合 WeFlow（消息读取）和 easyChat（UI自动化发送），
    支持 AI Agent 自动回复。
    """
    pass


# ── start: 启动服务 ──────────────────────────────────────────────
@cli.command()
@click.option("--host", default=None, help="监听地址")
@click.option("--port", type=int, default=None, help="监听端口")
@click.option("--weflow-url", default=None, help="WeFlow API 地址")
@click.option("--weflow-token", default=None, help="WeFlow Token")
@click.option("--agent-webhook", default=None, help="AI Agent 回调 URL")
@click.option("--auto-reply", is_flag=True, help="启用自动回复")
@click.option("--log-level", default=None, help="日志级别")
def start(host, port, weflow_url, weflow_token, agent_webhook, auto_reply, log_level):
    """启动 WeChat CLI 服务

    启动 HTTP API 服务并连接 WeFlow SSE 消息推送。
    配合 --agent-webhook 可实现 AI Agent 自动回复。
    """
    config = _load_config()

    # 覆盖命令行参数
    if host:
        config.host = host
    if port:
        config.port = port
    if weflow_url:
        config.weflow_url = weflow_url
    if weflow_token:
        config.weflow_token = weflow_token
    if agent_webhook:
        config.agent_webhook = agent_webhook
    if auto_reply:
        config.auto_reply_enabled = True
    if log_level:
        config.log_level = log_level

    _save_config(config)
    setup_logging(config.log_level)

    if config.effective_read_driver == "weflow":
        _ensure_weflow_api(config, wait_seconds=12.0)

    banner = f"""[bold cyan]WeChat CLI[/bold cyan] v0.1.0
[green]API 服务:[/green]     http://{config.host}:{config.port}
[green]WeFlow:[/green]       {config.weflow_url}
[green]Agent Webhook:[/green] {config.agent_webhook or '(未设置)'}
[green]自动回复:[/green]     {'✓ 已启用' if config.auto_reply_enabled else '✗ 已关闭'}
[green]配置文件:[/green]     {_get_config_path()}
"""
    console.print(Panel(banner, title="🤖 启动中...", border_style="cyan"))

    import uvicorn
    from .server import create_app
    app = create_app(config)

    # 在后台启动 Bridge 的 SSE 订阅
    async def start_bridge():
        bridge = app._agent_bridge if hasattr(app, '_agent_bridge') else None
        # Bridge 会在 API 请求时延迟启动

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower(),
    )


# ── status: 查看状态 ──────────────────────────────────────────────
@cli.command()
@click.option("--weflow-url", default=None)
@click.option("--weflow-token", default=None)
def status(weflow_url, weflow_token):
    """检查当前驱动状态"""
    config = _load_config()
    if weflow_url:
        config.weflow_url = weflow_url
    if weflow_token:
        config.weflow_token = weflow_token

    read_driver = config.effective_read_driver
    send_driver = config.effective_send_driver
    if read_driver == "native" or send_driver == "native":
        native_status = get_native_driver_status(config.wechat_data_path)
        if read_driver == "weflow":
            _ensure_weflow_api(config, wait_seconds=8.0)
        WeFlowClient = _get_weflow_client_class()
        weflow_ok = (
            asyncio.run(WeFlowClient(config.weflow_url, config.weflow_token).health())
            if read_driver == "weflow"
            else False
        )
        read_ready = native_status["read_ready"] if read_driver == "native" else weflow_ok
        send_ready = native_status["send_ready"] if send_driver == "native" else False
        table = Table(title="驱动状态")
        table.add_column("项目", style="bold")
        table.add_column("状态")
        table.add_row("平台", native_status["platform"])
        table.add_row("读取通道", read_driver)
        table.add_row("发送通道", send_driver)
        table.add_row("微信进程", "已发现" if native_status["wechat_running"] else "未发现微信进程")
        table.add_row("数据库", native_status["db_path"] or "未发现")
        table.add_row("数据库格式", native_status.get("db_format", "unknown"))
        if read_driver == "weflow":
            table.add_row("WeFlow API", f"已连接 ({config.weflow_url})" if weflow_ok else f"未连接 ({config.weflow_url})")
        table.add_row("读取状态", "可用" if read_ready else "不可用")
        table.add_row("发送状态", "可用" if send_ready else "不可用")
        console.print(table)

        missing = [
            name
            for name, available in native_status["dependencies"].items()
            if not available
        ]
        if missing:
            console.print(f"[yellow]缺少依赖:[/yellow] {', '.join(missing)}")
        if not send_ready and send_driver == "native":
            console.print("[yellow]发送通道不可用：请确认微信主程序已打开，且已安装 UI 自动化依赖。[/yellow]")
        if not read_ready and read_driver == "native":
            console.print("[yellow]读取通道不可用：当前原生数据库格式暂不支持直接读取，请使用 WeFlow。[/yellow]")
        return

    async def _check():
        WeFlowClient = _get_weflow_client_class()
        wf = WeFlowClient(config.weflow_url, config.weflow_token)
        healthy = await wf.health()
        if healthy:
            console.print(f"[green]✓[/green] WeFlow 连接成功 ({config.weflow_url})")
            sessions = await wf.get_sessions(limit=5)
            console.print(f"  会话数: {len(sessions)} (显示前5个)")
            for s in sessions[:5]:
                console.print(f"    - {s.get('displayName', '?')} ({s.get('username', '?')})")
        else:
            console.print(f"[red]✗[/red] WeFlow 连接失败 ({config.weflow_url})")
            console.print("  请确保 WeFlow 已启动，且 设置 → API 服务 → 启动服务 已开启")

    asyncio.run(_check())


# ── sessions: 会话列表 ──────────────────────────────────────────
@cli.command()
@click.option("--keyword", "-k", default=None, help="关键词过滤")
@click.option("--limit", "-n", type=int, default=20, help="返回数量")
@click.option("--json-output", "-j", is_flag=True, help="JSON 输出")
def sessions(keyword, limit, json_output):
    """列出微信会话"""
    config = _load_config()

    async def _list():
        WeFlowClient = _get_weflow_client_class()
        wf = WeFlowClient(config.weflow_url, config.weflow_token)
        try:
            data = await wf.get_sessions(keyword=keyword, limit=limit)
        except Exception as e:
            if not _ensure_weflow_api(config):
                print_weflow_unavailable_error(e)
                return
            data = await wf.get_sessions(keyword=keyword, limit=limit)
        if json_output:
            click.echo(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            table = Table(title="会话列表")
            table.add_column("序号", style="dim")
            table.add_column("名称", style="bold")
            table.add_column("ID", style="dim")
            table.add_column("类型")
            table.add_column("未读", style="yellow")
            for i, s in enumerate(data, 1):
                table.add_row(
                    str(i),
                    _table_cell(s.get("displayName")),
                    _table_cell(s.get("username")),
                    _table_cell(s.get("type")),
                    _table_cell(s.get("unreadCount"), "0"),
                )
            console.print(table)

    asyncio.run(_list())


# ── contacts: 联系人列表 ──────────────────────────────────────────
@cli.command()
@click.option("--keyword", "-k", default=None, help="关键词过滤")
@click.option("--limit", "-n", type=int, default=20, help="返回数量")
@click.option("--json-output", "-j", is_flag=True, help="JSON 输出")
def contacts(keyword, limit, json_output):
    """列出微信联系人"""
    config = _load_config()

    async def _list():
        WeFlowClient = _get_weflow_client_class()
        wf = WeFlowClient(config.weflow_url, config.weflow_token)
        try:
            data = await wf.get_contacts(keyword=keyword, limit=limit)
        except Exception as e:
            if not _ensure_weflow_api(config):
                print_weflow_unavailable_error(e)
                return
            data = await wf.get_contacts(keyword=keyword, limit=limit)
        if json_output:
            click.echo(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            table = Table(title="联系人列表")
            table.add_column("序号", style="dim")
            table.add_column("名称", style="bold")
            table.add_column("wxid", style="dim")
            for i, c in enumerate(data, 1):
                table.add_row(
                    str(i),
                    _table_cell(c.get("displayName", c.get("nickname"))),
                    _table_cell(c.get("username")),
                )
            console.print(table)

    asyncio.run(_list())


# ── messages: 消息历史 ──────────────────────────────────────────
@cli.command()
@click.argument("talker")
@click.option("--limit", "-n", type=int, default=20, help="返回条数")
@click.option("--json-output", "-j", is_flag=True, help="JSON 输出")
def messages(talker, limit, json_output):
    """查看指定会话的消息历史

    TALKER: 会话 ID (wxid 或 xxx@chatroom)
    """
    config = _load_weflow_config()

    try:
        data = _weflow_get(
            "/api/v1/messages",
            {"talker": talker, "limit": limit, "offset": 0},
            config,
        )
    except (HTTPError, URLError, TimeoutError) as e:
        if not _ensure_weflow_api(config):
            print_weflow_unavailable_error(e)
            return
        try:
            data = _weflow_get(
                "/api/v1/messages",
                {"talker": talker, "limit": limit, "offset": 0},
                config,
            )
        except (HTTPError, URLError, TimeoutError) as retry_error:
            print_weflow_unavailable_error(retry_error)
            return

    msgs = data.get("messages", [])
    if json_output:
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        console.print(f"[bold]会话: {talker}[/bold] (共 {data.get('count', 0)} 条)")
        for m in msgs:
            sender = "我" if m.get("isSend") else m.get("senderUsername", "?")
            content = m.get("parsedContent", m.get("content", ""))
            time_str = m.get("createTime", "")
            console.print(f"  [dim]{time_str}[/dim] [{sender}]: {content[:100]}")


# ── send: 发送消息 ──────────────────────────────────────────────
@cli.command()
@click.argument("to")
@click.argument("content")
@click.option("--at", multiple=True, help="@的用户")
def send(to, content, at):
    """发送消息到微信

    TO: 接收者显示名称（好友备注/昵称 或 群聊名称，不是 wxid！）
    CONTENT: 消息内容
    """
    started_at = time.perf_counter()
    config = _load_send_config()
    console.print(f"[dim]send startup +{time.perf_counter() - started_at:.3f}s[/dim] 读取发送配置")

    async def _send():
        console.print(f"发送到: [cyan]{to}[/cyan]")
        console.print(f"内容:   {content[:100]}")
        console.print()

        send_driver = "native" if config["use_native_driver"] else config["send_driver"]
        if send_driver == "native":
            import_start = time.perf_counter()
            native_send_handler = _get_native_send_handler()
            console.print(f"[dim]send startup +{time.perf_counter() - started_at:.3f}s[/dim] 加载 native 发送模块 ({time.perf_counter() - import_start:.3f}s)")

            def print_progress(label: str, elapsed: float) -> None:
                console.print(f"[dim]native send +{elapsed:.3f}s[/dim] {label}")

            success = await native_send_handler(to, content, progress=print_progress)
            _SendRequest, SendResponse = _get_send_models()
            result = SendResponse(
                success=success,
                message=f"发送成功 → {to}" if success else "",
                error=None if success else "原生 UI 驱动发送失败",
            )
        else:
            SendRequest, _SendResponse = _get_send_models()
            req = SendRequest(to=to, content=content, at=list(at) if at else None)
            EasyChatClient = _get_easychat_client_class()
            easychat = EasyChatClient()
            ok = await easychat.initialize()
            if not ok:
                console.print("[red]✗ easyChat 不可用[/red]")
                console.print("  发送消息需要 Windows 环境 + easyChat")
                console.print("  请参考: https://github.com/LTEnjoy/easyChat")
                return
            result = await easychat.send_message(req)

        if result.success:
            console.print(f"[green]✓ 发送成功[/green] → {to}")
        else:
            console.print(f"[red]✗ 发送失败: {result.error}[/red]")

    asyncio.run(_send())


# ── resolve: 名称解析 ──────────────────────────────────────────
@cli.command()
@click.argument("name_or_id")
def resolve(name_or_id):
    """查询联系人名称对应的 wxid，或 wxid 对应的显示名称

    NAME_OR_ID: 要查询的名称或 wxid
    """
    config = _load_config()

    async def _resolve():
        WeFlowClient = _get_weflow_client_class()
        wf = WeFlowClient(config.weflow_url, config.weflow_token)
        try:
            await wf.preload_names()
        except Exception as e:
            if not _ensure_weflow_api(config):
                print_weflow_unavailable_error(e)
                return
            await wf.preload_names()

        resolver = wf.name_resolver
        # 双向查询
        name = resolver.get_name(name_or_id)
        wid = resolver.get_id(name_or_id)

        if name:
            console.print(f"wxid → 名称: [cyan]{name_or_id}[/cyan] → [green]{name}[/green]")
        if wid:
            console.print(f"名称 → wxid: [cyan]{name_or_id}[/cyan] → [green]{wid}[/green]")
        if not name and not wid:
            console.print(f"[yellow]未找到匹配: {name_or_id}[/yellow]")
            console.print("  请确认 WeFlow 已启动且已连接微信数据库")

    asyncio.run(_resolve())


# ── config: 配置管理 ──────────────────────────────────────────
@cli.group()
def config_group():
    """管理配置"""
    pass


@config_group.command("show")
def config_show():
    """显示当前配置"""
    config = _load_config()
    data = config.model_dump()
    for k, v in data.items():
        if k.lower() in {"weflow_token", "agent_api_key"}:
            v = v[:8] + "..." if v else "(未设置)"
        console.print(f"  {k}: [cyan]{v}[/cyan]")
    console.print(f"\n  配置文件: [dim]{_get_config_path()}[/dim]")


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """设置配置项"""
    config = _load_config()
    if not hasattr(config, key):
        console.print(f"[red]✗ 未知配置项: {key}[/red]")
        return

    old_val = getattr(config, key)
    # 类型转换
    if isinstance(old_val, bool):
        value = value.lower() in ("true", "1", "yes")
    elif isinstance(old_val, int):
        value = int(value)
    elif isinstance(old_val, list):
        value = [v.strip() for v in value.split(",") if v.strip()]

    setattr(config, key, value)
    _save_config(config)
    console.print(f"[green]✓[/green] {key} = {value}")


# 添加 config 别名
cli.add_command(config_group, "config")


# ── agent: Agent 管理 ──────────────────────────────────────────
@cli.group()
def agent():
    """AI Agent 管理"""
    pass


@agent.command("set")
@click.argument("webhook_url")
@click.option("--api-key", default=None, help="Agent API Key")
def agent_set(webhook_url, api_key):
    """设置 AI Agent Webhook URL

    WEBHOOK_URL: Agent 的回调地址，如 http://localhost:8000/webhook
    """
    config = _load_config()
    config.agent_webhook = webhook_url
    if api_key:
        config.agent_api_key = api_key
    _save_config(config)
    console.print(f"[green]✓[/green] Agent Webhook: {webhook_url}")


@agent.command("test")
def agent_test():
    """测试 Agent 连通性"""
    config = _load_config()
    if not config.agent_webhook:
        console.print("[red]✗ 未设置 Agent Webhook[/red]")
        console.print("  运行: wechat-cli agent set <URL>")
        return

    async def _test():
        import httpx
        headers = {"Content-Type": "application/json"}
        if config.agent_api_key:
            headers["Authorization"] = f"Bearer {config.agent_api_key}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    config.agent_webhook,
                    json={
                        "message": {
                            "session_id": "test",
                            "session_type": "private",
                            "sender_name": "测试",
                            "content": "ping",
                            "message_type": "text",
                            "timestamp": 0,
                            "message_id": "test-001",
                            "is_self": False,
                        },
                        "history": [],
                    },
                    headers=headers,
                )
                if resp.status_code == 200:
                    console.print(f"[green]✓[/green] Agent 响应正常: {resp.json()}")
                else:
                    console.print(f"[yellow]⚠ Agent 返回 {resp.status_code}: {resp.text[:200]}[/yellow]")
        except Exception as e:
            console.print(f"[red]✗ 连接失败: {e}[/red]")

    asyncio.run(_test())


@agent.command("enable")
def agent_enable():
    """启用自动回复"""
    config = _load_config()
    config.auto_reply_enabled = True
    _save_config(config)
    console.print("[green]✓ 自动回复已启用[/green]")


@agent.command("disable")
def agent_disable():
    """禁用自动回复"""
    config = _load_config()
    config.auto_reply_enabled = False
    _save_config(config)
    console.print("[yellow]自动回复已关闭[/yellow]")


cli.add_command(agent)


def main():
    cli()


if __name__ == "__main__":
    main()
