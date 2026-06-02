import unittest
from unittest.mock import patch

from click.testing import CliRunner

from wechat_cli.cli import send, sessions
from wechat_cli.models import ServerConfig


class FakeWeFlowClient:
    def __init__(self, *_args, **_kwargs):
        pass

    async def get_sessions(self, keyword=None, limit=20):
        return [
            {
                "displayName": "测试会话",
                "username": "wxid_test",
                "type": 1,
                "unreadCount": 0,
            }
        ]


class CliRenderingTest(unittest.TestCase):
    def test_sessions_accepts_numeric_weflow_fields(self):
        runner = CliRunner()

        with patch("wechat_cli.cli._get_weflow_client_class", return_value=FakeWeFlowClient):
            result = runner.invoke(sessions, ["--limit", "1"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("测试会话", result.output)
        self.assertIn("wxid_test", result.output)

    def test_send_uses_native_driver_when_enabled(self):
        runner = CliRunner()
        calls = []

        async def fake_native_send_handler(to, content, progress=None):
            if progress:
                progress("mock发送", 0.001)
            calls.append((to, content))
            return True

        class UnexpectedEasyChatClient:
            def __init__(self, *_args, **_kwargs):
                raise AssertionError("native driver mode should not initialize easyChat")

        with (
            patch("wechat_cli.cli._load_config", return_value=ServerConfig(use_native_driver=True)),
            patch("wechat_cli.cli._get_easychat_client_class", return_value=UnexpectedEasyChatClient),
            patch("wechat_cli.cli._get_native_send_handler", return_value=fake_native_send_handler),
        ):
            result = runner.invoke(send, ["文件传输助手", "send-test"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(calls, [("文件传输助手", "send-test")])
        self.assertIn("发送成功", result.output)


if __name__ == "__main__":
    unittest.main()
