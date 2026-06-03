import unittest
from pathlib import Path
from unittest.mock import patch

from wechat_cli.weflow_runtime import ensure_weflow_api, is_local_weflow_url


class WeFlowRuntimeTest(unittest.TestCase):
    def test_local_url_detection(self):
        self.assertTrue(is_local_weflow_url("http://127.0.0.1:5031"))
        self.assertTrue(is_local_weflow_url("http://localhost:5031"))
        self.assertFalse(is_local_weflow_url("http://192.168.1.10:5031"))

    def test_ensure_returns_running_when_api_is_ready(self):
        with (
            patch("wechat_cli.weflow_runtime.probe_weflow_api", return_value=True),
            patch("wechat_cli.weflow_runtime.launch_weflow") as launch_weflow,
        ):
            ok, status = ensure_weflow_api("http://127.0.0.1:5031")

        self.assertTrue(ok)
        self.assertEqual(status, "running")
        launch_weflow.assert_not_called()

    def test_ensure_does_not_launch_remote_weflow_url(self):
        with (
            patch("wechat_cli.weflow_runtime.probe_weflow_api", return_value=False),
            patch("wechat_cli.weflow_runtime.launch_weflow") as launch_weflow,
        ):
            ok, status = ensure_weflow_api("http://192.168.1.10:5031")

        self.assertFalse(ok)
        self.assertEqual(status, "remote-unavailable")
        launch_weflow.assert_not_called()

    def test_ensure_launches_local_weflow_and_waits_for_api(self):
        with (
            patch("wechat_cli.weflow_runtime.probe_weflow_api", side_effect=[False, False, True]),
            patch("wechat_cli.weflow_runtime.launch_weflow", return_value=Path("C:/WeFlow/WeFlow.exe")),
            patch("wechat_cli.weflow_runtime.time.sleep"),
        ):
            ok, status = ensure_weflow_api(
                "http://127.0.0.1:5031",
                wait_seconds=1.0,
                poll_interval=0.01,
            )

        self.assertTrue(ok)
        self.assertTrue(status.startswith("started:"))


if __name__ == "__main__":
    unittest.main()
