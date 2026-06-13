import ctypes
from ctypes import wintypes
import threading
import time
import sys

# Windows Constants
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RIM_TYPEKEYBOARD = 1
WH_KEYBOARD_LL = 13
VK_A = 0x41
VK_B = 0x42

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

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD), ("flags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

# Structure for SendInput
class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# --- App State ---
last_event = {"hDevice": None, "vkey": None, "time": 0}
lock = threading.Lock()
target_device = None
mapping = {VK_A: VK_B} # 'A' becomes 'B'

def press_key(vk):
    # Send Key Down
    inputs = (INPUT * 2)()
    inputs[0].type = 1 # INPUT_KEYBOARD
    inputs[0].u.ki.wVk = vk
    inputs[0].u.ki.dwFlags = 0

    # Send Key Up
    inputs[1].type = 1
    inputs[1].u.ki.wVk = vk
    inputs[1].u.ki.dwFlags = 2 # KEYEVENTF_KEYUP

    user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))

def raw_input_loop():
    def wnd_proc(hwnd, msg, wparam, lparam):
        if msg == WM_INPUT:
            size = wintypes.UINT()
            user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
            if size.value > 0:
                buffer = ctypes.create_string_buffer(size.value)
                user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, buffer, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                raw = RAWINPUT.from_buffer(buffer)
                if raw.header.dwType == RIM_TYPEKEYBOARD:
                    with lock:
                        last_event["hDevice"] = raw.header.hDevice
                        last_event["vkey"] = raw.data.keyboard.VKey
                        last_event["time"] = time.time()
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    proc_ptr = WNDPROC(wnd_proc)
    class_name = "KeyboardAppWindow"
    class WNDCLASSEX(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON), ("hCursor", wintypes.HCURSOR), ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]

    wc = WNDCLASSEX()
    wc.cbSize = ctypes.sizeof(WNDCLASSEX); wc.lpfnWndProc = proc_ptr; wc.hInstance = kernel32.GetModuleHandleW(None); wc.lpszClassName = class_name
    user32.RegisterClassExW(ctypes.byref(wc))
    hwnd = user32.CreateWindowExW(0, class_name, "Hidden", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
    rid = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd)
    user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

def hook_callback(nCode, wParam, lParam):
    global target_device
    if nCode >= 0:
        kb = KBDLLHOOKSTRUCT.from_address(lParam)

        # Avoid recursion by ignoring injected keys
        if kb.flags & 0x10: # LLKHF_INJECTED
            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        with lock:
            current = last_event.copy()

        # Match with Raw Input (50ms window)
        if current["vkey"] == kb.vkCode and (time.time() - current["time"]) < 0.05:
            # Identification mode
            if target_device is None:
                target_device = current["hDevice"]
                print(f"\n[OK] Clavier identifié (Handle: {target_device})")
                print("Action: La touche 'A' de ce clavier écrira désormais 'B'.")
                return 0

            # Active remapping for target device
            if current["hDevice"] == target_device:
                if kb.vkCode in mapping:
                    # Handle only Key Down events to avoid double trigger
                    if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
                        print(f"Transformation: {hex(kb.vkCode)} -> {hex(mapping[kb.vkCode])}")
                        press_key(mapping[kb.vkCode])
                    return 1 # Block original key

    return user32.CallNextHookEx(None, nCode, wParam, lParam)

def main():
    if sys.platform != "win32":
        print("Erreur : Ce logiciel nécessite Windows.")
        return

    print("=== Logiciel de Personnalisation de Clavier ===")
    print("1. Appuyez sur n'importe quelle touche du clavier à modifier pour l'identifier.")

    threading.Thread(target=raw_input_loop, daemon=True).start()

    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    ptr = HOOKPROC(hook_callback)
    hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, ptr, kernel32.GetModuleHandleW(None), 0)

    try:
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        pass
    finally:
        user32.UnhookWindowsHookEx(hook)

if __name__ == "__main__":
    main()
