<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/WeChat-4.0+-07C160?logo=wechat&logoColor=white" alt="WeChat 4.0+">
  <img src="https://img.shields.io/badge/Status-Educational-red" alt="Status: Educational Use Only">
</p>

<h1 align="center">🤖 WeChat CLI</h1>

<p align="center">
  <b>让 AI 接管你的微信 —— 开源微信 Agent 自动回复框架</b>
</p>

<p align="center">
  ⚠️ <b>重要声明：本项目仅供个人学习、研究及技术交流使用，严禁用于任何商业用途或非法活动。</b>
</p>

---

## 🛑 免责声明 (Disclaimer)

**在使用本项目之前，请务必仔细阅读以下条款：**

1. **合规性**：本项目通过技术手段（包括但不限于 UI 自动化、内存读取）实现与微信客户端的交互。这些手段可能违反《微信软件许可及服务协议》。**使用本项目存在被微信官方封号的风险**，开发者对此不承担任何责任。
2. **数据隐私**：本项目所有操作均在本地完成，不会上传用户的任何聊天记录、密钥或个人信息。用户需妥善保管本地生成的任何数据。
3. **法律责任**：用户使用本项目从事的任何行为及其后果由用户自行承担。严禁利用本项目从事监听、窃取他人隐私、群发骚扰信息等违法违规行为。
4. **非官方**：本项目为非官方开源项目，与腾讯公司或微信官方无任何关联。

---

## ✨ 为什么选择 WeChat CLI？

| 痛点 | WeChat CLI 的解法 |
|------|-------------------|
| 📦 依赖多且重 | **内置原生驱动**，直接读取微信数据库 & 操作 UI，实现研究级的一键集成 |
| 🔒 隐私泄露 | **本地提 Key**，不修改微信客户端，不连接第三方解密服务 |
| 🤖 想让 AI 回复 | 内置 Agent Bridge，支持 **OpenAI / Claude / Ollama** 等任意 LLM |
| ⚙️ 配置复杂 | CLI 一行命令搞定，也支持运行时热更新配置 |

## 🚀 驱动模式说明

- **Native Driver (研究用)**: 自动从微信进程提取密钥，直接解密读取 `MSG.db`。此模式旨在演示跨进程内存访问和数据库解密原理。
- **Legacy Mode**: 兼容模式，支持通过第三方 API 服务进行交互。

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
```

## ⚡ 快速开始

### 1. 安装

```bash
git clone https://github.com/Mouseww/wechat-cli.git
cd wechat-cli
pip install -e .

# 安装依赖 (Windows)
pip install uiautomation pyperclip pycryptodome psutil
```

### 2. 配置与启动

```bash
# 启用原生驱动模式
wechat-cli config set use_native_driver true

# 检查状态
wechat-cli status

# 启动服务
wechat-cli start
```

## 🔧 CLI 命令大全

```bash
wechat-cli start                    启动服务
wechat-cli status                   查看驱动状态与密钥信息
wechat-cli send "张三" "你好"       原生驱动发送消息
```

---
<p align="center">
  <b>如果觉得有用，请给个 ⭐ Star 支持一下！</b>
</p>
