import ctypes
from ctypes import wintypes
import sys

# Windows Constants
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RIM_TYPEKEYBOARD = 1

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]

class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]

class RAWINPUT(ctypes.Structure):
    class _Data(ctypes.Union):
        # We only care about keyboard for now. Mouse and HID are larger/different.
        # But we must ensure the union is large enough or we just use the header to find the type.
        _fields_ = [
            ("keyboard", RAWKEYBOARD),
            # Add padding for mouse/hid if needed, but for Keyboard it's fine
        ]
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", _Data),
    ]

def monitor_keyboards():
    if sys.platform != "win32":
        print("Note: This script is designed for Windows and will not run on this Linux environment.")
        return

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            size = wintypes.UINT()
            user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))

            if size.value > 0:
                buffer = ctypes.create_string_buffer(size.value)
                user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, buffer, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                raw = RAWINPUT.from_buffer(buffer)

                if raw.header.dwType == RIM_TYPEKEYBOARD:
                    kb = raw.data.keyboard
                    # Flags: 0=Down, 1=Up, 2=E0 (Extended), 4=E1
                    is_up = kb.Flags & 0x01
                    event_type = "Up" if is_up else "Down"
                    print(f"Device Handle: {raw.header.hDevice}, VKey: {hex(kb.VKey)}, Event: {event_type}")

        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    proc_ptr = WNDPROC(wnd_proc)

    class_name = "KeyboardMonitorWindow"
    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC),
            ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
            ("hIcon", wintypes.HICON), ("hCursor", wintypes.HCURSOR), ("hbrBackground", wintypes.HBRUSH),
            ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON),
        ]

    wc = WNDCLASSEX()
    wc.cbSize = ctypes.sizeof(WNDCLASSEX)
    wc.lpfnWndProc = proc_ptr
    wc.hInstance = kernel32.GetModuleHandleW(None)
    wc.lpszClassName = class_name
    user32.RegisterClassExW(ctypes.byref(wc))

    hwnd = user32.CreateWindowExW(0, class_name, "Hidden", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)

    rid = RAWINPUTDEVICE()
    rid.usUsagePage = 0x01
    rid.usUsage = 0x06
    rid.dwFlags = RIDEV_INPUTSINK
    rid.hwndTarget = hwnd
    user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))

    print("Monitoring keyboards (Raw Input)... Press Ctrl+C to stop.")
    msg = wintypes.MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    monitor_keyboards()
