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

## 🛑 免责声明与开发说明 (Developer Statement)

**本项目的开发方式与合规声明：**

1. **开发方式声明**：本项目代码中的内存读取、数据库解密、UI 自动化等技术实现，**完全基于公开的通用技术原理**（如 Windows API `ReadProcessMemory`、SQLCipher 解密流程、UIA 自动化协议）。开发者在编写代码的过程中，**未对微信客户端进行任何形式的逆向工程、调试、反编译或注入操作**。所有技术细节均来源于公开资料、操作系统文档、以及社区公开讨论。

2. **合规性**：本项目通过技术手段（包括但不限于 UI 自动化、内存读取）实现与微信客户端的交互。这些手段可能违反《微信软件许可及服务协议》。**使用本项目存在被微信官方封号的风险**，开发者对此不承担任何责任。

3. **数据隐私**：本项目所有操作均在本地完成，不会上传用户的任何聊天记录、密钥或个人信息。用户需妥善保管本地生成的任何数据。

4. **法律责任**：用户使用本项目从事的任何行为及其后果由用户自行承担。严禁利用本项目从事监听、窃取他人隐私、群发骚扰信息等违法违规行为。

5. **非官方**：本项目为非官方开源项目，与腾讯公司或微信官方无任何关联。

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

### 2. 安装并启动 WeFlow

完整环境需要同时运行 WeFlow。`sessions`、`contacts`、`messages`、名称解析、SSE 新消息订阅和自动回复链路都依赖 WeFlow HTTP API；仅 UI 自动化发送可以在读取通道不可用时单独工作。

1. 安装并打开 WeFlow。
2. 在 WeFlow 中连接当前微信账号的数据源。
3. 打开 WeFlow 的 API 服务，默认地址应为 `http://127.0.0.1:5031`。
4. 如启用了 Token，在后续命令中配置 `weflow_token`。

可用以下命令检查 WeFlow API：

```bash
curl http://127.0.0.1:5031/health
```

WeFlow API 文档参考：https://weflow.imsry.cn/api-reference

### 3. 配置与启动

```bash
# 默认读取使用 WeFlow，发送使用原生 UI 自动化
wechat-cli config set read_driver weflow
wechat-cli config set send_driver native
wechat-cli config set use_native_driver false

# 配置 WeFlow API
wechat-cli config set weflow_url http://127.0.0.1:5031

# 检查状态
wechat-cli status

# 启动服务
wechat-cli start
```

## 🧠 让大模型安装完整环境

仓库内置了一个安装 Skill，可交给支持 Skills 的大模型直接执行完整安装和验收：

```text
Use the skill at skills/wechat-cli-installer to install the full WeChat CLI environment on Windows.
```

该 Skill 会引导大模型完成 Python 环境、Windows UI 自动化依赖、WeFlow API、CLI 配置、发送通道和读取通道的检查。

## 🔧 CLI 命令大全

```bash
wechat-cli start                    启动服务
wechat-cli status                   查看驱动状态与密钥信息
wechat-cli send "张三" "你好"       原生驱动发送消息
```

## 🪟 Windows 微信 4.x 发送配置指南

### 环境要求

- Windows 桌面端微信已打开并登录。
- 微信主窗口保持可见，不要最小化。
- 已安装发送依赖：

```bash
pip install uiautomation pyperclip psutil
```

### 发送前检查

```bash
wechat-cli status
```

默认模式下 `wechat-cli status` 应显示读取通道为 `weflow`、发送通道为 `native`。读取依赖 WeFlow API；发送依赖 Windows 微信主程序和 UI 自动化依赖。

### 发送消息

```bash
wechat-cli send "文件传输助手" "测试发送"
wechat-cli send "Webber" "测试发送"
```

`TO` 必须是微信里能搜索到的好友备注、昵称或群聊名称。CLI 会先通过微信搜索打开目标会话，再把内容粘贴到当前会话输入区并发送，避免误发到当前焦点所在的聊天窗口。

### 微信 4.x Qt 窗口兼容

部分微信 4.x 客户端的主窗口类名不是旧版 `WeChatMainWndForPC`，而是 `Qt51514QWindowIcon`。当前原生驱动会按以下顺序查找窗口：

1. `WeChatMainWndForPC`
2. `Qt51514QWindowIcon` + 标题 `微信`
3. 标题 `微信`

如果 UIAutomation 无法识别微信内部输入框，驱动会在搜索并打开目标会话后，点击窗口底部输入区域作为回退路径，再粘贴并发送消息。

---
<p align="center">
  <b>如果觉得有用，请给个 ⭐ Star 支持一下！</b>
</p>
