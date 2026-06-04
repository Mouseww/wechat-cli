"""Hakimi gateway stream buffering for non-editable WeChat chats."""
from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional

logger = logging.getLogger("wechat-cli.hakimi_stream")

SendSegment = Callable[[str, str, dict], Awaitable[bool]]


@dataclass
class StreamState:
    chat_id: str
    trace: dict
    text: str = ""
    flushed_until: int = 0
    idle_task: Optional[asyncio.Task] = None
    started_at: float = 0.0
    updated_at: float = 0.0
    flush_lock: Optional[asyncio.Lock] = None

    def __post_init__(self):
        self.flush_lock = asyncio.Lock()


class HakimiStreamBuffer:
    """Buffers Hakimi edit-style streaming and emits complete WeChat bubbles."""

    def __init__(self, send_segment: SendSegment, idle_flush_seconds: float = 1.2):
        self._send_segment = send_segment
        self._idle_flush_seconds = idle_flush_seconds
        self._next_id = 0
        self._states: Dict[int, StreamState] = {}

    def next_message_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def trace_for_message(self, message_id: int) -> dict:
        state = self._states.get(message_id)
        return state.trace if state else {}

    async def start(self, chat_id: str, text: str, trace: Optional[dict] = None) -> dict:
        message_id = self.next_message_id()
        now = time.perf_counter()
        self._states[message_id] = StreamState(
            chat_id=chat_id,
            trace=trace or {},
            started_at=now,
            updated_at=now,
        )
        trace_id = self._states[message_id].trace.get("trace_id", "")
        logger.info(
            "trace=%s Hakimi 流式缓冲开始: message_id=%s chat_id=%s initial_chars=%d since_poll=%s",
            trace_id or "-",
            message_id,
            chat_id,
            len(text),
            self._format_since(trace, "polled_at", now),
        )
        flushed = await self.update(message_id, text)
        return {"message_id": message_id, "flushed": flushed}

    async def update(self, message_id: int, text: str) -> int:
        state = self._states.get(message_id)
        if state is None:
            logger.debug("忽略未知 Hakimi 虚拟消息更新: message_id=%s", message_id)
            return 0

        now = time.perf_counter()
        logger.info(
            "trace=%s Hakimi 流式更新: message_id=%s chat_id=%s chars=%d since_stream_start=%.3fs since_poll=%s",
            state.trace.get("trace_id", "-"),
            message_id,
            state.chat_id,
            len(text),
            now - state.started_at,
            self._format_since(state.trace, "polled_at", now),
        )
        # 在获取锁之前取消旧的 idle task，防止它在我们等锁期间触发
        if state.idle_task and not state.idle_task.done():
            state.idle_task.cancel()
        async with state.flush_lock:
            # 必须在锁内修改 text 和 flushed_until，
            # 否则并发的 flush_message 会读到新 text + 旧 flushed_until，
            # 把旧尾段和新内容混在一起发出，导致重复
            state.text = text
            state.updated_at = now
            if state.flushed_until > len(text):
                state.flushed_until = 0
            flushed = await self._flush_complete_paragraphs(state)
        self._schedule_idle_flush(message_id)
        return flushed

    async def flush_message(self, message_id: int) -> int:
        state = self._states.get(message_id)
        if state is None:
            return 0
        # 只取消 idle task 当它不是当前正在执行的任务时，避免自我取消导致消息永远不发送
        current = asyncio.current_task()
        if state.idle_task and not state.idle_task.done() and state.idle_task is not current:
            state.idle_task.cancel()
        async with state.flush_lock:
            segment = state.text[state.flushed_until :].strip()
            if not segment:
                return 0
            if await self._send_segment(state.chat_id, segment, state.trace):
                state.flushed_until = len(state.text)
                logger.info(
                    "trace=%s Hakimi 流式尾段发送: message_id=%s chat_id=%s chars=%d since_stream_start=%.3fs since_receive=%s",
                    state.trace.get("trace_id", "-"),
                    message_id,
                    state.chat_id,
                    len(segment),
                    time.perf_counter() - state.started_at,
                    self._format_since(state.trace, "received_at"),
                )
                return 1
            return 0

    async def _flush_complete_paragraphs(self, state: StreamState) -> int:
        flushed = 0
        while True:
            # 允许单换行直接作为分段气泡界限
            match = re.search(r"\n+", state.text[state.flushed_until :])
            if not match:
                return flushed
            start = state.flushed_until + match.start()
            end = state.flushed_until + match.end()
            segment = state.text[state.flushed_until : start].strip()
            state.flushed_until = end
            if not segment:
                continue
            if await self._send_segment(state.chat_id, segment, state.trace):
                flushed += 1
                logger.info(
                    "trace=%s Hakimi 流式段落发送: chat_id=%s chars=%d since_stream_start=%.3fs since_receive=%s",
                    state.trace.get("trace_id", "-"),
                    state.chat_id,
                    len(segment),
                    time.perf_counter() - state.started_at,
                    self._format_since(state.trace, "received_at"),
                )

    def _schedule_idle_flush(self, message_id: int) -> None:
        state = self._states.get(message_id)
        if state is None:
            return
        if state.idle_task and not state.idle_task.done():
            state.idle_task.cancel()
        state.idle_task = asyncio.create_task(self._idle_flush_later(message_id))

    async def _idle_flush_later(self, message_id: int) -> None:
        try:
            await asyncio.sleep(self._idle_flush_seconds)
            await self.flush_message(message_id)
        except asyncio.CancelledError:
            return

    def _format_since(
        self,
        trace: Optional[dict],
        key: str,
        now: Optional[float] = None,
    ) -> str:
        if not trace or key not in trace:
            return "-"
        current = now if now is not None else time.perf_counter()
        return f"{current - float(trace[key]):.3f}s"
