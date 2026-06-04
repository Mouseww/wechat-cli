import sys, ctypes

user32 = ctypes.windll.user32
matches = []
def _class_name(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value

def _window_text(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    result = user32.SendMessageTimeoutW(hwnd, 0x000D, 256, buffer, 0x0002, 100, ctypes.byref(ctypes.c_ulong(0)))
    if result: return buffer.value
    return ''

def enum_proc(hwnd, lparam):
    if not user32.IsWindowVisible(hwnd): return True
    cn = _class_name(hwnd)
    title = _window_text(hwnd)
    if '微信' in title or 'WeChat' in cn:
        safe_title = title.encode('utf-8', errors='ignore').decode('utf-8')
        print(f'HWND: {hwnd}, Class: {cn}, Title: {safe_title}')
    return True

callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_proc)
user32.EnumWindows(callback, 0)
