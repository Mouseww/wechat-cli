#!/usr/bin/env python3
"""
AI Agent Webhook (OpenAI 兼容) - 接入真实 LLM 的自动回复示例

支持 OpenAI、Claude (via proxy)、本地 Ollama 等 OpenAI 兼容 API。

启动方式：
    export OPENAI_API_KEY=sk-xxx
    export OPENAI_BASE_URL=https://api.openai.com/v1
    python agent_openai.py

    # 使用 Ollama 本地模型:
    export OPENAI_BASE_URL=http://localhost:11434/v1
    export OPENAI_API_KEY=ollama
    export MODEL_NAME=qwen2.5:7b
"""
import os
import json
import logging
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-openai")

app = FastAPI(title="WeChat AI Agent")

# 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "你是一个智能微信助手。用户通过微信给你发消息，你需要简洁、友好地回复。"
    "回复要简短自然，像微信聊天一样，不要使用 markdown 格式。"
    "如果消息不需要回复（比如纯表情、已读内容等），返回 [SKIP]。"
)

GROUP_SYSTEM_PROMPT = os.getenv(
    "GROUP_SYSTEM_PROMPT",
    "你是一个群聊中的智能助手。只有当有人明确向你提问或需要帮助时才回复。"
    "回复要简洁。如果消息不需要你回复，返回 [SKIP]。"
)

# 消息历史（内存存储，生产环境建议用 Redis）
_histories: dict[str, list] = {}
MAX_HISTORY = 20


async def call_llm(messages: list[dict]) -> str:
    """调用 OpenAI 兼容 API"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "max_tokens": 500,
        "temperature": 0.7,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{OPENAI_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()

    msg = data.get("message", {})
    context = data.get("context", {})

    sender = msg.get("sender_name", "未知")
    content = msg.get("content", "").strip()
    session_id = msg.get("session_id", "")
    session_name = msg.get("session_name", "")
    session_type = msg.get("session_type", "private")
    is_group = session_type == "group"
    reply_target = context.get("reply_target", session_name)

    # 跳过非文本消息
    msg_type = msg.get("message_type", "text")
    if msg_type != "text":
        return JSONResponse({"reply": None, "action": "skip"})

    if not content:
        return JSONResponse({"reply": None, "action": "skip"})

    logger.info(f"收到: [{reply_target}] {sender}: {content[:100]}")

    # 构建对话历史
    history = _histories.get(session_id, [])
    system_prompt = GROUP_SYSTEM_PROMPT if is_group else SYSTEM_PROMPT

    messages = [{"role": "system", "content": system_prompt}]

    for h in history[-MAX_HISTORY:]:
        messages.append(h)

    user_msg = f"[{sender}]: {content}" if is_group else content
    messages.append({"role": "user", "content": user_msg})

    try:
        reply = await call_llm(messages)
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return JSONResponse({"reply": None, "action": "skip"})

    if "[SKIP]" in reply or "SKIP" == reply.strip():
        logger.info("LLM 决定跳过此消息")
        return JSONResponse({"reply": None, "action": "skip"})

    reply = reply.replace("[SKIP]", "").strip()
    if not reply:
        return JSONResponse({"reply": None, "action": "skip"})

    # 保存对话历史
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": reply})
    _histories[session_id] = history[-MAX_HISTORY:]

    logger.info(f"回复 → [{reply_target}]: {reply[:100]}")
    return JSONResponse({"reply": reply, "action": "reply"})


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/clear/{session_id}")
async def clear_history(session_id: str):
    _histories.pop(session_id, None)
    return {"success": True}


if __name__ == "__main__":
    print("=" * 50)
    print("  WeChat AI Agent (OpenAI 兼容)")
    print(f"  模型: {MODEL_NAME}")
    print(f"  API:  {OPENAI_BASE_URL}")
    print("  监听: http://localhost:9000/webhook")
    print("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=9000)
