<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/WeChat-4.0+-07C160?logo=wechat&logoColor=white" alt="WeChat 4.0+">
  <img src="https://img.shields.io/badge/Driver-Native-orange?logo=cpu&logoColor=white" alt="Native Driver">
</p>

<h1 align="center">🤖 WeChat CLI</h1>

<p align="center">
  <b>让 AI 接管你的微信 —— 开源微信 Agent 自动回复框架</b>
</p>

<p align="center">
  内置原生驱动，<b>不再需要安装 WeFlow 或 easyChat</b><br>
  提供 CLI + HTTP API，一行命令让任何 AI 大模型自动回复微信消息
</p>

---

## ✨ 为什么选择 WeChat CLI？

| 痛点 | WeChat CLI 的解法 |
|------|-------------------|
| 📦 依赖多且重 | **内置原生驱动**，直接读取微信数据库 & 操作 UI，零外部软件依赖 |
| 🔒 隐私泄露 | **本地提 Key**，不修改微信客户端，不连接第三方解密服务 |
| 🤖 想让 AI 回复 | 内置 Agent Bridge，支持 **OpenAI / Claude / Ollama** 等任意 LLM |
| 🎯 消息定位难 | 智能名称解析（`NameResolver`），wxid ↔ 显示名称自动映射 |
| ⚙️ 配置复杂 | CLI 一行命令搞定，也支持运行时热更新配置 |

## 🚀 核心驱动模式

- **Native Driver (推荐)**: 自动从微信进程提取密钥，直接解密读取 `MSG.db`，通过原生 UI Automation 发送消息。**无需安装 WeFlow/easyChat。**
- **Legacy Mode**: 兼容模式，仍支持通过 WeFlow API 和 easyChat 服务进行交互。

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
│  │         Native Driver (DB Reader + UI Sender)         │  │
│  │        自动提 Key / 实时监听 / 原生 UI 自动化         │  │
│  └────────────────────────┬───────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────┘
                            │
                  ┌─────────┴─────────┐
                  │    AI Agent        │
                  │  Webhook 回调      │
                  │ GPT / Claude / ... │
                  └────────────────────┘
```

## ⚡ 快速开始

### 1. 安装

```bash
git clone https://github.com/Mouseww/wechat-cli.git
cd wechat-cli
pip install -e .

# 安装原生驱动依赖 (Windows)
pip install uiautomation pyperclip pycryptodome psutil
```

### 2. 配置与启动

```bash
# 启用原生驱动模式（不再需要 WeFlow）
wechat-cli config set use_native_driver true

# 检查连接（会自动尝试提取微信密钥）
wechat-cli status

# 启动服务
wechat-cli start
```

## 🧠 3 分钟接入 AI Agent

```python
# agent_openai.py —— 用 OpenAI API 自动回复
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

async def handle_message(msg: dict):
    # 你的 AI 逻辑...
    return "回复内容"
```

## 🔧 CLI 命令大全

```bash
# ── 基础操作 ──────────────────────────────
wechat-cli start                    启动服务
wechat-cli status                   查看驱动状态与密钥信息
wechat-cli send "张三" "你好"       原生驱动发送消息
wechat-cli resolve wxid_xxx         查询名称映射

# ── 配置管理 ──────────────────────────────
wechat-cli config set use_native_driver true
wechat-cli config set auto_reply_enabled true
```

## ❓ FAQ

**Q: 需要安装 WeFlow 吗？**
A: 最新版不再需要。WeChat CLI 现在可以直接从内存提取密钥并解密数据库。

**Q: 支持微信哪些版本？**
A: 完美支持微信 4.0+ 桌面版（Windows）。

---
<p align="center">
  <b>如果觉得有用，请给个 ⭐ Star 支持一下！</b>
</p>
