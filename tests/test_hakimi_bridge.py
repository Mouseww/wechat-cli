import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
import httpx

from wechat_cli.models import ServerConfig, SessionType, WeChatMessage
from wechat_cli.server import create_app
from wechat_cli.hakimi_stream import HakimiStreamBuffer
from wechat_cli.weflow_client import WeFlowClient


class HakimiBridgeTest(unittest.TestCase):
    def test_messages_endpoint_returns_distinct_wechat_sessions_as_chat_ids(self):
        app = create_app(ServerConfig(auto_reply_enabled=False))
        bridge = app.state.bridge

        asyncio.run(
            bridge._on_new_message(
                WeChatMessage(
                    session_id="wxid_alice",
                    session_name="Alice",
                    session_type=SessionType.PRIVATE,
                    sender_name="Alice",
                    content="你好",
                    message_id="m1",
                )
            )
        )
        asyncio.run(
            bridge._on_new_message(
                WeChatMessage(
                    session_id="room1@chatroom",
                    session_name="项目群",
                    group_name="项目群",
                    session_type=SessionType.GROUP,
                    sender_name="Bob",
                    content="进度如何",
                    message_id="m2",
                )
            )
        )

        client = TestClient(app)
        response = client.get("/messages")

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["next_offset"], "2")
        self.assertEqual(
            [item["chat_id"] for item in body["messages"]],
            ["wxid_alice", "room1@chatroom"],
        )
        self.assertEqual(body["messages"][0]["text"], "你好")
        self.assertEqual(body["messages"][1]["conversation_name"], "项目群")

    def test_send_message_resolves_chat_id_to_wechat_display_name(self):
        app = create_app(ServerConfig(auto_reply_enabled=False))
        bridge = app.state.bridge
        bridge.remember_reply_target("wxid_alice", "Alice")
        calls = []

        async def fake_send(req, trace=None):
            calls.append((req.to, req.content))
            return type("SendResult", (), {"success": True, "error": None})()

        bridge.send = fake_send

        client = TestClient(app)
        response = client.post(
            "/send_message",
            json={"chat_id": "wxid_alice", "text": "Hakimi 回复"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        asyncio.run(app.state.hakimi_stream.flush_message(response.json()["message_id"]))
        self.assertEqual(calls, [("Alice", "Hakimi 回复")])
        self.assertTrue(response.json()["success"])

    def test_send_message_suppresses_hakimi_tool_progress(self):
        app = create_app(ServerConfig(auto_reply_enabled=False))
        bridge = app.state.bridge
        bridge.remember_reply_target("wxid_alice", "Alice")
        calls = []

        async def fake_send(req, trace=None):
            calls.append((req.to, req.content))
            return type("SendResult", (), {"success": True, "error": None})()

        bridge.send = fake_send

        client = TestClient(app)
        response = client.post(
            "/send_message",
            json={"chat_id": "wxid_alice", "text": "⚙️ skill_manage (action: list)"},
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["success"])
        self.assertTrue(response.json()["suppressed"])
        self.assertEqual(calls, [])

    def test_hakimi_stream_buffers_initial_fragment_until_paragraph_boundary(self):
        calls = []

        async def fake_send(chat_id, text, trace):
            calls.append((chat_id, text))
            return True

        buffer = HakimiStreamBuffer(fake_send, idle_flush_seconds=10)

        result = asyncio.run(buffer.start("wxid_alice", "好"))
        self.assertEqual(result["flushed"], 0)
        self.assertEqual(calls, [])

        flushed = asyncio.run(buffer.update(result["message_id"], "好的。\n\n我可以帮你查资料。"))
        self.assertEqual(flushed, 1)
        self.assertEqual(calls, [("wxid_alice", "好的。")])

    def test_hakimi_stream_flushes_tail_segment_on_idle(self):
        calls = []

        async def fake_send(chat_id, text, trace):
            calls.append((chat_id, text))
            return True

        buffer = HakimiStreamBuffer(fake_send, idle_flush_seconds=10)
        result = asyncio.run(buffer.start("wxid_alice", "这是最后一段"))

        flushed = asyncio.run(buffer.flush_message(result["message_id"]))
        self.assertEqual(flushed, 1)
        self.assertEqual(calls, [("wxid_alice", "这是最后一段")])

    def test_send_and_edit_message_emit_wechat_bubble_on_complete_paragraph(self):
        app = create_app(ServerConfig(auto_reply_enabled=False))
        bridge = app.state.bridge
        bridge.remember_reply_target("wxid_alice", "Alice")
        calls = []

        async def fake_send(req, trace=None):
            calls.append((req.to, req.content))
            return type("SendResult", (), {"success": True, "error": None})()

        bridge.send = fake_send

        client = TestClient(app)
        response = client.post(
            "/send_message",
            json={"chat_id": "wxid_alice", "text": "好"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        message_id = response.json()["message_id"]
        self.assertEqual(calls, [])

        edit_response = client.post(
            "/edit_message",
            json={
                "chat_id": "wxid_alice",
                "message_id": message_id,
                "text": "好的。\n\n我可以帮你查资料。",
            },
        )
        self.assertEqual(edit_response.status_code, 200, edit_response.text)
        self.assertEqual(calls, [("Alice", "好的。")])

    def test_hakimi_bridge_keeps_rapid_messages_from_same_session(self):
        app = create_app(ServerConfig(auto_reply_enabled=False))
        bridge = app.state.bridge

        for message_id, content in (("m1", "第一条"), ("m2", "第二条")):
            asyncio.run(
                bridge._on_new_message(
                    WeChatMessage(
                        session_id="wxid_alice",
                        session_name="Alice",
                        session_type=SessionType.PRIVATE,
                        sender_name="Alice",
                        content=content,
                        message_id=message_id,
                    )
                )
            )

        client = TestClient(app)
        response = client.get("/messages")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            [item["text"] for item in response.json()["messages"]],
            ["第一条", "第二条"],
        )

    def test_weflow_sse_403_logs_actionable_push_setup_hint(self):
        client = WeFlowClient("http://127.0.0.1:5031", "token")

        response = httpx.Response(
            403,
            request=httpx.Request("GET", "http://127.0.0.1:5031/api/v1/push/messages"),
        )

        async def fake_stream(*args, **kwargs):
            raise httpx.HTTPStatusError("forbidden", request=response.request, response=response)

        with (
            patch("wechat_cli.weflow_client._stream_sse_once", new=AsyncMock(side_effect=fake_stream)),
            patch("wechat_cli.weflow_client.asyncio.sleep", new=AsyncMock(side_effect=asyncio.CancelledError)),
            self.assertLogs("wechat-cli.weflow", level="ERROR") as logs,
        ):
            with self.assertRaises(asyncio.CancelledError):
                asyncio.run(client.subscribe_messages(lambda msg: None))

        self.assertTrue(
            any("主动推送" in line and "/api/v1/push/messages" in line for line in logs.output),
            logs.output,
        )


if __name__ == "__main__":
    unittest.main()
