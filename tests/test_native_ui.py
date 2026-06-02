import asyncio
import unittest
from unittest.mock import patch

from wechat_cli import native_ui


class NativeUiTest(unittest.TestCase):
    def test_native_send_handler_initializes_uiautomation_in_worker_thread(self):
        events = []

        class FakeInitializer:
            def __enter__(self):
                events.append("enter")
                return self

            def __exit__(self, *_args):
                events.append("exit")

        class FakeAuto:
            UIAutomationInitializerInThread = FakeInitializer

        class FakeNativeWeChatUI:
            def __init__(self, progress=None):
                self.progress = progress

            def send_text(self, to_name, content):
                events.append(("send", to_name, content))
                return True

        with (
            patch.object(native_ui, "auto", FakeAuto),
            patch.object(native_ui, "NativeWeChatUI", FakeNativeWeChatUI),
        ):
            ok = asyncio.run(native_ui.native_send_handler("文件传输助手", "send-test"))

        self.assertTrue(ok)
        self.assertEqual(events, ["enter", ("send", "文件传输助手", "send-test"), "exit"])

    def test_get_window_supports_weixin_qt_main_window(self):
        events = []

        class FakeWindow:
            def __init__(self, exists):
                self.exists = exists

            def Exists(self, _timeout):
                return self.exists

            def SetFocus(self):
                events.append("focus")

        class FakeAuto:
            @staticmethod
            def WindowControl(**kwargs):
                events.append(("window", kwargs))
                if kwargs == {"searchDepth": 1, "ClassName": "Qt51514QWindowIcon", "Name": "微信"}:
                    return FakeWindow(True)
                return FakeWindow(False)

            @staticmethod
            def SendKeys(keys):
                events.append(("keys", keys))

        with (
            patch.object(native_ui.sys, "platform", "linux"),
            patch.object(native_ui, "auto", FakeAuto),
        ):
            win = native_ui.NativeWeChatUI()._get_window()

        self.assertIsNotNone(win)
        self.assertIn(("window", {"searchDepth": 1, "ClassName": "WeChatMainWndForPC"}), events)
        self.assertIn(("window", {"searchDepth": 1, "ClassName": "Qt51514QWindowIcon", "Name": "微信"}), events)
        self.assertIn("focus", events)

    def test_send_text_uses_keyboard_fast_path(self):
        events = []
        sleeps = []

        class FakeRect:
            left = 0
            right = 1000
            bottom = 800

        class FakeControl:
            BoundingRectangle = FakeRect()

            def ButtonControl(self, **_kwargs):
                raise AssertionError("发送路径不应深度扫描 ButtonControl")

            def EditControl(self, **_kwargs):
                raise AssertionError("发送路径不应深度扫描 EditControl")

        class FakeAuto:
            @staticmethod
            def SendKeys(keys):
                events.append(("keys", keys))

            @staticmethod
            def Click(x, y):
                events.append(("click", x, y))

        with (
            patch.object(native_ui.sys, "platform", "linux"),
            patch.object(native_ui, "auto", FakeAuto),
            patch.object(native_ui.NativeWeChatUI, "_get_window", return_value=FakeControl()),
            patch.object(native_ui.pyperclip, "copy", lambda text: events.append(("copy", text))),
            patch.object(native_ui.time, "sleep", lambda seconds: sleeps.append(seconds)),
        ):
            ok = native_ui.NativeWeChatUI().send_text("文件传输助手", "send-test")

        self.assertTrue(ok)
        self.assertEqual(
            events,
            [
                ("keys", "{Ctrl}f"),
                ("copy", "文件传输助手"),
                ("keys", "{Ctrl}v"),
                ("keys", "{Enter}"),
                ("click", 620, 705),
                ("copy", "send-test"),
                ("keys", "{Ctrl}v"),
                ("keys", "{Enter}"),
            ],
        )
        self.assertLessEqual(sum(sleeps), 1.2)


if __name__ == "__main__":
    unittest.main()
