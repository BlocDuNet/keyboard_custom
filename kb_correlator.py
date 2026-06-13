import ctypes
from ctypes import wintypes
import queue
import threading
import time
import sys

# Windows Constants
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RIM_TYPEKEYBOARD = 1
WH_KEYBOARD_LL = 13

# Structures for Raw Input
class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT), ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD), ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode", wintypes.USHORT), ("Flags", wintypes.USHORT), ("Reserved", wintypes.USHORT), ("VKey", wintypes.USHORT), ("Message", wintypes.UINT), ("ExtraInformation", wintypes.ULONG)]

class RAWINPUT(ctypes.Structure):
    class _Data(ctypes.Union):
        _fields_ = [("keyboard", RAWKEYBOARD)]
    _fields_ = [("header", RAWINPUTHEADER), ("data", _Data)]

# Structure for Hook
class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

# Globals
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
last_raw_event = None
event_lock = threading.Lock()

def raw_input_thread():
    global last_raw_event

    def wnd_proc(hwnd, msg, wparam, lparam):
        global last_raw_event
        if msg == WM_INPUT:
            size = wintypes.UINT()
            user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
            if size.value > 0:
                buffer = ctypes.create_string_buffer(size.value)
                user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, buffer, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                raw = RAWINPUT.from_buffer(buffer)
                if raw.header.dwType == RIM_TYPEKEYBOARD:
                    with event_lock:
                        last_raw_event = {
                            "hDevice": raw.header.hDevice,
                            "vkey": raw.data.keyboard.VKey,
                            "time": time.time()
                        }
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    proc_ptr = WNDPROC(wnd_proc)
    class_name = "RawInputCorrelationWindow"
    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON), ("hCursor", wintypes.HCURSOR), ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]

    wc = WNDCLASSEX()
    wc.cbSize = ctypes.sizeof(WNDCLASSEX); wc.lpfnWndProc = proc_ptr; wc.hInstance = kernel32.GetModuleHandleW(None); wc.lpszClassName = class_name
    user32.RegisterClassExW(ctypes.byref(wc))
    hwnd = user32.CreateWindowExW(0, class_name, "Hidden", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)

    rid = RAWINPUTDEVICE()
    rid.usUsagePage = 0x01; rid.usUsage = 0x06; rid.dwFlags = RIDEV_INPUTSINK; rid.hwndTarget = hwnd
    user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

hook_id = None
def hook_callback(nCode, wParam, lParam):
    global last_raw_event
    if nCode >= 0:
        kb = KBDLLHOOKSTRUCT.from_address(lParam)

        # Correlate with last raw event
        with event_lock:
            current_raw = last_raw_event

        if current_raw and (time.time() - current_raw["time"]) < 0.05: # 50ms window
            if current_raw["vkey"] == kb.vkCode:
                # We have a match! We know which device sent this key.
                # Example: Block key 'A' ONLY from device with handle 0x12345
                # For demo, just print and allow/block based on a condition
                print(f"Key {hex(kb.vkCode)} matched to Device {current_raw['hDevice']}")

                # If we want to remap:
                # 1. Block this key (return 1)
                # 2. Use SendInput to send the new key

    return user32.CallNextHookEx(hook_id, nCode, wParam, lParam)

if __name__ == "__main__":
    if sys.platform != "win32":
        print("Designed for Windows.")
    else:
        threading.Thread(target=raw_input_thread, daemon=True).start()

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        callback_ptr = HOOKPROC(hook_callback)
        hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback_ptr, kernel32.GetModuleHandleW(None), 0)

        print("Correlated monitoring started. Press Ctrl+C.")
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        except KeyboardInterrupt:
            user32.UnhookWindowsHookEx(hook_id)
