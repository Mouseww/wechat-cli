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

1. **开发方式声明**：本项目代码中的数据库解密、UI 自动化等技术实现，**完全基于公开的通用技术原理**（如 Windows API `ReadProcessMemory`、SQLCipher 解密流程、UIA 自动化协议）。开发者在编写代码的过程中，**未对微信客户端进行任何形式的逆向工程、调试、反编译或注入操作**。所有技术细节均来源于公开资料、操作系统文档、以及社区公开讨论。

2. **合规性**：本项目通过技术手段（包括但不限于 UI 自动化、内存读取）实现与微信客户端的交互。这些手段可能违反《微信软件许可及服务协议》。**使用本项目存在被微信官方封号的风险**，开发者对此不承担任何责任。

3. **数据隐私**：本项目所有操作均在本地完成，不会上传用户的任何聊天记录、密钥或个人信息。用户需妥善保管本地生成的任何数据。

4. **法律责任**：用户使用本项目从事的任何行为及其后果由用户自行承担。严禁利用本项目从事监听、窃取他人隐私、群发骚扰信息等违法违规行为。

5. **非官方**：本项目为非官方开源项目，与腾讯公司或微信官方无任何关联。

---

## ✨ 项目定位

WeChat CLI 是一个运行在本机的微信 sidecar，用于把桌面微信接到 CLI、HTTP API 和 Agent 自动回复链路。

| 场景 | 能力边界 |
|------|----------|
| 命令行查看微信数据 | 通过 WeFlow HTTP API 查询会话、联系人和历史消息 |
| 命令行发送消息 | 通过 Windows 微信窗口执行 UI 自动化发送 |
| 接入 AI Agent | 监听新消息，转发到 webhook，并按 Agent 返回结果回复 |
| 接入 Hakimi | 提供 `clawbot` 兼容的 `/messages`、`/send_message`、`/edit_message` 端点 |
| 本机安装 | `install.bat` 创建虚拟环境、安装依赖、检测 WeFlow 并写入默认配置 |

## 部分截图
<img width="416" height="212" alt="image" src="https://github.com/user-attachments/assets/7510375d-3bc7-41f9-943c-693c30748f8a" />
<img width="1836" height="954" alt="image" src="https://github.com/user-attachments/assets/44456c3c-d720-4974-a3ba-369bb24784c0" />


## 🚀 驱动模式说明

- **读取通道 `read_driver=weflow`（默认）**：`sessions`、`contacts`、`messages`、名称解析、SSE 新消息订阅和自动回复链路依赖 WeFlow HTTP API。
- **发送通道 `send_driver=native`（默认）**：文本发送通过 Windows 微信主窗口完成，需要微信已登录、主窗口可见。

默认组合是 `WeFlow 读取 + native 发送`。这两个能力是独立的：读取不可用时，UI 自动化发送仍可单独验证；发送可用也不代表 WeFlow 已配置完成。

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
│  │       Driver Layer: WeFlow Reader + Native Sender      │  │
│  │       会话/消息读取走 WeFlow，消息发送走微信 UI        │  │
│  └────────────────────────┬───────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────┘
```

## ⚡ 快速开始

### 1. 安装依赖

Windows 推荐直接运行一键安装脚本。脚本会创建 `.venv`、安装 Python 依赖、检测 WeFlow；如果 WeFlow API 不可用，会自动下载并启动 WeFlow 安装程序。

```powershell
git clone https://github.com/Mouseww/wechat-cli.git
cd wechat-cli
.\install.bat
```

也可以直接运行 PowerShell 脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

安装脚本会写入默认配置：

```powershell
wechat-cli config set read_driver weflow
wechat-cli config set send_driver native
wechat-cli config set use_native_driver false
wechat-cli config set weflow_url http://127.0.0.1:5031
```

如果全局命令暂不可用，可以直接使用虚拟环境入口：

```powershell
.\.venv\Scripts\python.exe -m wechat_cli.cli status
```

### 2. 安装并启动 WeFlow

完整环境需要同时运行 WeFlow。`sessions`、`contacts`、`messages`、名称解析、SSE 新消息订阅和自动回复链路都依赖 WeFlow HTTP API；仅 UI 自动化发送可以在读取通道不可用时单独工作。一键安装脚本会在检测不到 WeFlow API 时自动安装 WeFlow。

1. 安装并打开 WeFlow。
2. 在 WeFlow 中连接当前微信账号的数据源。
3. 打开 WeFlow 的 API 服务，默认地址应为 `http://127.0.0.1:5031`。
4. 如启用了 Token，在后续命令中配置 `weflow_token`。

可用以下命令检查 WeFlow API：

```powershell
curl.exe http://127.0.0.1:5031/health
```

WeFlow API 文档参考：https://weflow.imsry.cn/api-reference

### 3. 配置与启动

```powershell
# 默认读取使用 WeFlow，发送使用原生 UI 自动化
wechat-cli config set read_driver weflow
wechat-cli config set send_driver native
wechat-cli config set use_native_driver false

# 配置 WeFlow API
wechat-cli config set weflow_url http://127.0.0.1:5031

# 检查状态
wechat-cli status

# 启动服务
wechat-cli start --log-level debug
```
WeChat CLI 本身也支持 AI 自动回复，可在 WebUI 中配置。

服务默认监听 `http://127.0.0.1:5032`。启动时如果读取通道是 WeFlow，且 `weflow_url` 是本机地址，服务会尝试检测并拉起本机 WeFlow。

健康检查：

```powershell
curl.exe http://127.0.0.1:5032/health
```

### 4. 接入 Hakimi 多会话 Gateway

Hakimi 是一个本地优先的多 Agent 助手运行时，可把 CLI、浏览器、消息网关等入口统一接到多会话 Agent 工作流。仓库地址：https://github.com/Mouseww/hakimi-agent

把微信作为 Hakimi 的聊天入口时，不要把所有微信消息转发到 Hakimi `/api/chat`；该接口是共享会话，容易让不同联系人串上下文。推荐让 Hakimi 使用已有的 `clawbot` HTTP bridge 模式轮询 `wechat-cli`：

```yaml
# ~/.hakimi/config.yaml
gateways:
  clawbot:
    enabled: true
    mode: "http_bridge"
    bot_id: "clawbot"
    base_url: "http://127.0.0.1:5032"
    poll_path: "/messages"
    send_path: "/send_message"
    edit_path: "/edit_message"
    poll_interval_ms: 1000
    poll_limit: 50
```

运行方式：

```powershell
# 终端 1：启动微信 sidecar。它会自动检查/启动 WeFlow，并监听微信消息。
wechat-cli start

# 终端 2：启动 Hakimi gateway。
hakimi --gateway
```

多会话映射规则：

- 微信 `session_id` 会作为 Hakimi gateway 的 `chat_id`。
- 不同联系人/群聊会进入 Hakimi 不同 chat 历史，避免上下文串线。
- Hakimi 回复时调用 `POST /send_message`，`wechat-cli` 会把 `chat_id` 映射回微信显示名称，再用原生 UI 发送。
- 只有先收到过消息的会话一定有显示名称映射；主动给未见过的 wxid 发消息仍建议先用微信显示名。

## 🧠 让大模型安装完整环境

仓库内置了一个安装 Skill，可交给支持 Skills 的大模型直接执行完整安装和验收：

```text
Use the skill at skills/wechat-cli-installer to install the full WeChat CLI environment on Windows.
```

该 Skill 会引导大模型完成 Python 环境、Windows UI 自动化依赖、WeFlow API、CLI 配置、发送通道和读取通道的检查。

## 🔧 CLI 命令大全

```powershell
wechat-cli status                         查看读取/发送通道状态
wechat-cli sessions --limit 10            查看最近会话
wechat-cli contacts --limit 10            查看联系人
wechat-cli messages "filehelper" --limit 5 查看历史消息
wechat-cli send "文件传输助手" "测试发送" 发送文本消息
wechat-cli webui                          打开 Web 配置界面
wechat-cli start --log-level debug         启动 HTTP API 和 Agent Bridge
```

Hakimi bridge 兼容端点：

```text
GET  /messages       Hakimi 轮询微信入站消息
POST /send_message   Hakimi 发送回复到微信
POST /edit_message   兼容 Hakimi 编辑式流式更新
```

通用 API：

```text
GET  /api/v1/sessions
GET  /api/v1/contacts
GET  /api/v1/messages?talker=<session_id>
POST /api/v1/send
GET  /api/v1/stats
```

## 🪟 Windows 微信 4.x 发送配置指南

### 环境要求

- Windows 桌面端微信已打开并登录。
- 微信主窗口保持可见，不要最小化。
- 已安装发送依赖：

```powershell
pip install uiautomation pyperclip psutil
```

### 发送前检查

```powershell
wechat-cli status
```

默认模式下 `wechat-cli status` 应显示读取通道为 `weflow`、发送通道为 `native`。读取依赖 WeFlow API；发送依赖 Windows 微信主程序和 UI 自动化依赖。

### 发送消息

```powershell
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

## 🧩 WebUI 与 Agent 自动回复

启动 WebUI：

```powershell
wechat-cli webui
```

默认地址是 `http://127.0.0.1:5033`，可配置 WeFlow URL、Token、读取/发送通道、Agent webhook、自动回复开关、白名单、黑名单和关键词。

Webhook 示例：

```powershell
python agent_example.py
wechat-cli agent set http://127.0.0.1:9000/webhook
wechat-cli agent enable
wechat-cli start --log-level debug
```

Agent 返回 `{"action":"reply","reply":"..."}` 时发送回复；返回 `{"action":"skip"}` 时跳过。

## 🧯 排障优先级

1. 先运行 `wechat-cli status`，确认读取通道和发送通道分别是否可用。
2. 读不到会话或消息时，先检查 `curl.exe http://127.0.0.1:5031/health` 和 WeFlow 账号数据源配置。
3. 发不出消息时，先保持 Windows 微信已登录、主窗口可见，再用 `wechat-cli send "文件传输助手" "测试发送"` 做最小验证。
4. Hakimi 或 Agent 没有回复时，用 `wechat-cli start --log-level debug` 查看是否出现 `Bridge 发送开始` 和 `native 发送开始` 日志。
5. 不要把服务暴露到公网；默认只建议监听 `127.0.0.1`。

---

<img width="141" height="51" alt="image" src="https://github.com/user-attachments/assets/bda11993-b65b-4e6c-969e-e6827d8e1a37" />

    Thanks to everyone on LinuxDo for their support!

---

<p align="center">
  <b>如果觉得有用，请给个 ⭐ Star 支持一下！</b>
</p>
