#!/usr/bin/env python3
"""
示例 Agent Webhook - 接收微信消息并自动生成回复

最简单的 AI Agent 对接示例，演示完整的回调协议。

启动方式：
    python agent_example.py

然后在另一个终端：
    wechat-cli agent set http://localhost:9000/webhook
    wechat-cli agent enable
    wechat-cli start
"""
import json
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-example")

app = FastAPI(title="WeChat Agent Example")


def generate_reply(sender: str, content: str, is_group: bool = False) -> str | None:
    """生成回复内容

    替换此函数以接入你的 AI Agent（OpenAI、Claude、本地模型等）
    返回 None 表示不回复
    """
    content = content.strip()
    if not content:
        return None

    # 群聊中只有特定关键词才回复
    if is_group:
        if "你好" in content or "hello" in content.lower():
            return f"你好 {sender}！有什么可以帮你的吗？"
        return None

    # 私聊自动回复
    if "你好" in content or "hi" in content.lower() or "hello" in content.lower():
        return f"你好！我是 AI 助手，有什么可以帮你的？"

    if "时间" in content:
        from datetime import datetime
        return f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    if "帮助" in content or "help" in content.lower():
        return "我可以帮你：\n1. 回答问题\n2. 查询时间\n3. 更多功能开发中..."

    # 默认回复
    return f"收到你的消息: '{content[:50]}'。我是自动回复机器人，如有紧急事务请直接联系本人。"


@app.post("/webhook")
async def webhook(request: Request):
    """接收 WeChat CLI 转发的消息

    请求格式：
    {
        "message": {
            "session_id": "wxid_xxx 或 xxx@chatroom",
            "session_name": "张三 或 群聊名称",  ← 会话显示名称
            "session_type": "private 或 group",
            "sender_name": "发送者昵称",
            "group_name": "群聊名称 (仅群聊)",
            "content": "消息内容",
            "message_type": "text",
            "timestamp": 1700000000,
            "message_id": "123456",
            "is_self": false
        },
        "history": [...],
        "context": {
            "session_type": "private",
            "is_group": false,
            "session_id": "wxid_xxx",
            "session_name": "张三",        ← 会话显示名称
            "group_name": null,
            "sender_name": "张三",
            "reply_target": "张三"         ← 回复目标名称
        }
    }

    响应格式：
    {
        "reply": "你好！有什么可以帮你的？",  ← 回复文本
        "action": "reply"                     ← reply/skip/forward
    }
    """
    data = await request.json()

    msg = data.get("message", {})
    context = data.get("context", {})

    sender = msg.get("sender_name", "未知")
    content = msg.get("content", "")
    session_type = msg.get("session_type", "private")
    is_group = session_type == "group"
    group_name = msg.get("group_name", "")
    reply_target = context.get("reply_target", "")

    logger.info(f"收到消息: [{reply_target}] {sender}: {content[:100]}")

    # 生成回复
    reply = generate_reply(sender, content, is_group)

    if reply:
        logger.info(f"生成回复: {reply[:100]}")
        return JSONResponse({
            "reply": reply,
            "action": "reply",
            # "reply_to": "其他联系人名称",  # 可选：回复到指定会话
        })
    else:
        logger.info("跳过此消息")
        return JSONResponse({
            "reply": None,
            "action": "skip",
        })


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    print("=" * 50)
    print("  WeChat Agent 示例 Webhook")
    print("  监听: http://localhost:9000/webhook")
    print("=" * 50)
    print()
    print("  配置方式:")
    print("    wechat-cli agent set http://localhost:9000/webhook")
    print("    wechat-cli agent enable")
    print("    wechat-cli start")
    print()

    uvicorn.run(app, host="0.0.0.0", port=9000)
