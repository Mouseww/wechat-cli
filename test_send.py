import sys, ctypes, time

def test_send():
    import wechat_cli.native_ui as ui
    u = ui.NativeWeChatUI()
    print("Testing get window")
    win = u._get_window()
    print(f"Window: {win}")
    if win:
        print("Testing send text")
        ui.NativeWeChatUI().send_text("Webber", "Test send from script directly")
        print("Sent")
    else:
        print("No window found")
test_send()
