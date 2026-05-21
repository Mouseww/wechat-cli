<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/WeChat-4.0+-07C160?logo=wechat&logoColor=white" alt="WeChat 4.0+">
  <img src="https://img.shields.io/badge/AI%20Agent-Ready-purple?logo=openai&logoColor=white" alt="AI Agent Ready">
</p>

<h1 align="center">🤖 WeChat CLI</h1>

<p align="center">
  <b>让 AI 接管你的微信 —— 开源微信 Agent 自动回复框架</b>
</p>

<p align="center">
  结合 <a href="https://github.com/hicccc77/WeFlow">WeFlow</a>（消息读取）和 <a href="https://github.com/LTEnjoy/easyChat">easyChat</a>（UI 自动化发送）<br>
  提供 CLI + HTTP API，一行命令让任何 AI 大模型自动回复微信消息
</p>

---

## ✨ 为什么选择 WeChat CLI？

| 痛点 | WeChat CLI 的解法 |
|------|-------------------|
| 🔒 微信没有官方开放 API | 基于 WeFlow 读取本地数据库 + easyChat UI 自动化，**不修改微信客户端** |
| 🤖 想让 AI 自动回复微信 | 内置 Agent Bridge，支持 **OpenAI / Claude / Ollama** 等任意 LLM |
| 🔌 第三方工具对接困难 | 统一 HTTP API + SSE 实时推送，**任何语言/框架都能接入** |
| 🎯 消息回复不到正确的人 | 智能名称解析（`NameResolver`），wxid ↔ 显示名称自动映射 |
| ⚙️ 配置复杂 | CLI 一行命令搞定，也支持运行时热更新配置 |

## 🚀 能做什么？

- **AI 自动回复** —— 接入 ChatGPT/Claude/Ollama，自动回复微信私聊和群聊
- **消息监控** —— 实时 SSE 推送，不漏掉任何一条新消息
- **群聊 @机器人** —— 支持关键词触发，只在被 @mention 或特定关键词时回复
- **消息转发** —— 把微信消息转发到 Discord / Slack / Telegram / 邮件
- **数据分析** —— 通过 API 导出聊天记录，做情感分析、关键词统计
- **自定义工作流** —— HTTP API 支持任意第三方工具对接

## 📐 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      WeChat CLI                              │
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌───────────────────┐   │
│  │   CLI    │   │  HTTP API    │   │   Agent Bridge    │   │
│  │ (click)  │   │  (FastAPI)   │   │  (SSE → Webhook)  │   │
│  └────┬─────┘   └──────┬───────┘   └────────┬──────────┘   │
│       │                │                     │              │
│  ┌────┴────────────────┴─────────────────────┴───────────┐  │
│  │              WeFlow Client + NameResolver              │  │
│  │         读取消息 / 会话 / SSE 推送 / 名称映射          │  │
│  └────────────────────────┬───────────────────────────────┘  │
│                           │                                  │
│  ┌────────────────────────┴───────────────────────────────┐  │
│  │             easyChat Client (可选, Windows)             │  │
│  │                UI 自动化发送消息 / 文件                  │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
          │                                        │
          ▼                                        ▼
  ┌───────────────┐                     ┌───────────────────┐
│  │   WeFlow      │                     │    AI Agent        │
│  │ (本地运行)     │                     │  Webhook 回调      │
│  │ 读取微信数据库 │                     │ GPT / Claude / ... │
│  └───────────────┘                     └───────────────────┘
```

## ⚡ 快速开始

### 1. 安装

```bash
git clone https://github.com/Mouseww/wechat-cli.git
cd wechat-cli
pip install -e .

# Windows 用户（需要发送功能时）
pip install -e ".[win]"
```

### 2. 启动 WeFlow

1. 下载 [WeFlow](https://github.com/hicccc77/WeFlow/releases) 并安装
2. 打开 WeFlow，连接微信数据库
3. 进入 **设置 → API 服务 → 启动服务**
4. （可选）开启 **主动推送** 以支持实时消息监听

### 3. 检查连接

```bash
wechat-cli status
```

### 4. 开始使用

```bash
# 方式 A：纯消息读取 + HTTP API
wechat-cli start

# 方式 B：接入 AI Agent 自动回复
wechat-cli agent set http://localhost:9000/webhook
wechat-cli agent enable
wechat-cli start
```

## 🧠 3 分钟接入 AI Agent

### 最简示例：自定义回复逻辑

```python
# agent_example.py —— 你的 Agent 只需实现一个 Webhook
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class WebhookRequest(BaseModel):
    message: dict
    context: dict

@app.post("/webhook")
async def handle(req: WebhookRequest):
    msg = req.message
    text = msg["content"]

    # 你的 AI 逻辑 —— 这里可以用任何 LLM
    reply = f"你说的是：{text}"

    return {"reply": reply, "action": "reply"}
```

```bash
# 启动你的 Agent
python agent_example.py

# 配置并启动 WeChat CLI
wechat-cli agent set http://localhost:9000/webhook
wechat-cli agent enable
wechat-cli start
```

### 接入 OpenAI / 任意 LLM

```python
# agent_openai.py —— 用 OpenAI API 自动回复
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),  # 兼容任意 OpenAI 格式 API
)

async def handle_message(msg: dict) -> str:
    response = client.chat.completions.create(
        model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": "你是一个微信智能助手，简洁友好地回复消息。"},
            {"role": "user", "content": msg["content"]},
        ],
        max_tokens=500,
    )
    return response.choices[0].message.content
```

> 💡 **兼容任意 OpenAI 格式 API**：设置 `OPENAI_BASE_URL` 即可接入 DeepSeek / Qwen / Ollama / vLLM 等

## 📡 HTTP API 参考

启动后默认监听 `http://127.0.0.1:5032`，所有端点支持 CORS。

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `GET` | `/api/v1/sessions` | 获取会话列表 |
| `GET` | `/api/v1/contacts` | 获取联系人列表 |
| `GET` | `/api/v1/messages` | 获取消息历史 |
| `POST` | `/api/v1/send` | 发送消息 |
| `POST` | `/api/v1/agent/callback` | Agent 主动回调 |
| `GET` | `/api/v1/stream/messages` | SSE 实时消息流 |
| `GET` | `/api/v1/stats` | 统计信息 |
| `POST` | `/api/v1/config` | 运行时更新配置 |

### 使用示例

```bash
# 获取最近 10 个会话
curl http://localhost:5032/api/v1/sessions?limit=10

# 获取某人的消息历史
curl "http://localhost:5032/api/v1/messages?talker=wxid_xxx&limit=20"

# 发送消息
curl -X POST http://localhost:5032/api/v1/send \
  -H "Content-Type: application/json" \
  -d '{"to": "张三", "content": "你好！"}'

# Agent 主动回调（不通过 Agent Bridge，直接调用发送）
curl -X POST http://localhost:5032/api/v1/agent/callback \
  -H "Content-Type: application/json" \
  -d '{"to": "工作群", "content": "📢 通知：系统维护中"}'

# 实时监听新消息（SSE）
curl -N http://localhost:5032/api/v1/stream/messages

# 运行时热更新配置
curl -X POST http://localhost:5032/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{"auto_reply_enabled": true, "reply_delay_ms": 2000}'
```

## 🔧 CLI 命令大全

```bash
# ── 基础操作 ──────────────────────────────
wechat-cli start                    启动服务（HTTP API + SSE 监听）
wechat-cli status                   查看 WeFlow 连接状态
wechat-cli sessions                 列出会话
wechat-cli sessions -k "工作" -n 10 搜索会话
wechat-cli contacts -k "张三"       搜索联系人
wechat-cli messages wxid_xxx -n 50  查看消息历史
wechat-cli send "张三" "你好"       发送消息
wechat-cli resolve wxid_xxx         查询 wxid ↔ 显示名称映射

# ── 配置管理 ──────────────────────────────
wechat-cli config show              查看当前配置
wechat-cli config set weflow_url http://127.0.0.1:5031
wechat-cli config set auto_reply_enabled true
wechat-cli config set reply_delay_ms 1000

# ── Agent 管理 ──────────────────────────────
wechat-cli agent set http://localhost:9000/webhook
wechat-cli agent set http://localhost:9000/webhook --api-key sk-xxx
wechat-cli agent test               测试 Agent 连通性
wechat-cli agent enable             启用自动回复
wechat-cli agent disable            禁用自动回复
```

## 🎯 智能过滤规则

不想让 AI 回复所有消息？精细控制触发条件：

```bash
# 只监听特定会话（白名单）
wechat-cli config set listen_sessions '["wxid_friend", "xxx@chatroom"]'

# 忽略特定会话（黑名单）
wechat-cli config set ignore_sessions '["wxid_spam"]'

# 只在包含关键词时触发（群聊 @机器人 场景）
wechat-cli config set listen_keywords '["@机器人", "帮助", "help"]'
```

也支持运行时动态更新：

```bash
curl -X POST http://localhost:5032/api/v1/config \
  -H "Content-Type: application/json" \
  -d '{
    "listen_sessions": ["wxid_friend"],
    "listen_keywords": ["@机器人"]
  }'
```

## 🔌 集成示例

### n8n / Make / Zapier

通过 HTTP API 接入低代码自动化平台：

```
触发器：WeChat CLI SSE → n8n Webhook
动作：n8n 处理逻辑 → WeChat CLI /api/v1/send
```

### LangChain / LlamaIndex

```python
import httpx

def wechat_tool(content: str, to: str):
    """LangChain Tool: 通过 WeChat CLI 发送消息"""
    resp = httpx.post("http://localhost:5032/api/v1/send", json={
        "to": to,
        "content": content,
    })
    return resp.json()
```

### Discord / Telegram 转发

```python
# 微信消息 → Telegram 转发
import httpx, asyncio

async def forward_to_telegram():
    async with httpx.AsyncClient() as client:
        async with client.stream("GET", "http://localhost:5032/api/v1/stream/messages") as sse:
            async for line in sse.aiter_lines():
                # 解析 SSE 事件，转发到 Telegram Bot API
                ...
```

## 📋 Webhook 协议

### 请求格式（WeChat CLI → 你的 Agent）

```json
{
  "message": {
    "session_id": "wxid_xxx",
    "session_name": "张三",
    "session_type": "private",
    "sender_id": "wxid_sender",
    "sender_name": "张三",
    "group_name": null,
    "content": "你好",
    "message_type": "text",
    "timestamp": 1700000000,
    "message_id": "123456",
    "is_self": false
  },
  "history": [/* 最近 N 条消息作为上下文 */],
  "context": {
    "session_type": "private",
    "is_group": false
  }
}
```

### 响应格式（你的 Agent → WeChat CLI）

```json
{
  "reply": "你好！有什么可以帮你的？",
  "action": "reply"
}
```

支持的 action：
- `reply` — 发送回复
- `skip` — 跳过不回复
- `forward` — 转发消息

## ❓ FAQ

**Q: 需要修改微信客户端吗？**
A: 不需要。WeFlow 读取本地数据库，easyChat 通过 UI 自动化操作，都不修改微信客户端本身。

**Q: 支持微信哪些版本？**
A: 微信 4.0+ 桌面版（Windows/macOS）。发送功能目前仅支持 Windows（easyChat 依赖 UI 自动化）。

**Q: 安全吗？会被封号吗？**
A: WeFlow 是只读的数据库查看工具，easyChat 模拟人工操作。但自动化操作始终存在风险，建议：
- 设置合理的 `reply_delay_ms`（≥1000ms）
- 不要高频发送相同内容
- 仅用于个人/开发用途

**Q: 能在 Linux/macOS 上运行吗？**
A: 消息读取（WeFlow）和 HTTP API 可以在所有平台运行。发送功能需要 Windows 上运行 easyChat。

**Q: 支持群聊吗？**
A: 支持。可以自动识别群聊消息，支持 @mention 触发，回复到正确的群聊。

## 🛠️ 环境要求

- Python 3.9+
- [WeFlow](https://github.com/hicccc77/WeFlow)（必须）— 消息读取
- [easyChat](https://github.com/LTEnjoy/easyChat)（可选）— 消息发送，仅 Windows
- 微信 4.0+ 桌面版

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 打开 Pull Request

## 📄 License

MIT License — 自由使用、修改和分发。

## 🙏 致谢

- [WeFlow](https://github.com/hicccc77/WeFlow) — 微信聊天记录查看与 HTTP API
- [easyChat](https://github.com/LTEnjoy/easyChat) — PC 端微信 UI 自动化

---

<p align="center">
  <b>如果觉得有用，请给个 ⭐ Star 支持一下！</b>
</p>
