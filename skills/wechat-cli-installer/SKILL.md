---
name: wechat-cli-installer
description: Install and validate the full WeChat CLI environment on Windows, including Python package setup, Windows UI automation dependencies, WeFlow API setup, CLI configuration, status checks, and send/read smoke tests. Use when a user asks an AI agent to install, repair, configure, or verify this repository end to end.
---

# WeChat CLI Installer

Install from the repository root. Treat this as a Windows desktop setup: WeChat Desktop and WeFlow must be installed and visible/running before full validation can pass.

## Workflow

1. Check the environment:

```powershell
python --version
git status --short
Get-Process | Where-Object { $_.ProcessName -like '*WeChat*' }
```

2. Create or use a local virtual environment:

```powershell
& "./install.bat"
```

3. Require WeFlow for the complete environment:

- The install script checks WeFlow API.
- If WeFlow API is unavailable, the script downloads the latest Windows x64 WeFlow installer from GitHub Releases and starts it.
- Complete the WeFlow installer when prompted.
- Connect WeFlow to the active WeChat account/data source.
- Enable WeFlow API service.
- Use `http://127.0.0.1:5031` unless the user provides another URL.
- If WeFlow requires a token, ask the user for it before saving it.

4. Configure WeChat CLI:

```powershell
& ".venv/Scripts/python.exe" -m wechat_cli.cli config set read_driver weflow
& ".venv/Scripts/python.exe" -m wechat_cli.cli config set send_driver native
& ".venv/Scripts/python.exe" -m wechat_cli.cli config set use_native_driver false
& ".venv/Scripts/python.exe" -m wechat_cli.cli config set weflow_url http://127.0.0.1:5031
```

When a token is provided:

```powershell
& ".venv/Scripts/python.exe" -m wechat_cli.cli config set weflow_token "<TOKEN>"
```

5. Validate:

```powershell
& ".venv/Scripts/python.exe" -m py_compile wechat_cli/native_ui.py
& ".venv/Scripts/python.exe" -m wechat_cli.cli --help
& ".venv/Scripts/python.exe" -m wechat_cli.cli status
curl.exe http://127.0.0.1:5031/health
```

6. Smoke test capabilities:

```powershell
& ".venv/Scripts/python.exe" -m wechat_cli.cli sessions --limit 5
& ".venv/Scripts/python.exe" -m wechat_cli.cli send "文件传输助手" "测试发送"
```

Only send a real message after the user confirms the target and content.

## Expected Results

- `wechat-cli status` should show Windows platform and WeChat process discovered.
- `发送通道` should be `可用` when WeChat Desktop is open and UI automation dependencies are installed.
- WeFlow `/health` should respond before claiming read/session/message features are ready.
- `sessions`, `contacts`, `messages`, name resolution, SSE subscriptions, and auto-reply workflows require WeFlow.

## Common Fixes

- If `wechat-cli send` opens the target chat but does not paste content, keep the WeChat window visible and retry after focusing the main window.
- If WeChat 4.x uses a Qt window, `native_ui.py` should support `Qt51514QWindowIcon`.
- If the console fails on Chinese or emoji text, run inside a UTF-8 capable terminal.
- If read features fail while send works, fix WeFlow first; native UI sending does not prove WeFlow is configured.
