import ctypes
from ctypes import wintypes
import threading
import time
import sys
import tkinter as tk
from tkinter import ttk, messagebox

# --- Windows Constants & Structures ---
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RIM_TYPEKEYBOARD = 1
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104

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

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Setup 64-bit safe signatures
user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, ctypes.POINTER(wintypes.UINT), wintypes.UINT]
user32.GetRawInputData.restype = wintypes.UINT
user32.RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]
user32.RegisterRawInputDevices.restype = wintypes.BOOL
user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HWND, wintypes.HANDLE, wintypes.HINSTANCE, wintypes.LPVOID]
user32.CreateWindowExW.restype = wintypes.HWND
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.DefWindowProcW.restype = ctypes.c_longlong
user32.SetWindowsHookExW.argtypes = [ctypes.c_int, ctypes.c_void_p, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HANDLE
user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_longlong
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

# --- App Logic ---
class KeyboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Keyboard Customizer (64-bit)")
        self.root.geometry("500x400")

        self.last_raw_event = {"hDevice": None, "vkey": None, "time": 0}
        self.lock = threading.Lock()
        self.target_handle = None
        self.mapping_active = False
        self.mapping = {0x41: 0x42} # A -> B

        self.setup_ui()
        self.start_threads()

    def setup_ui(self):
        self.status_label = ttk.Label(self.root, text="Statut : Prêt", font=("Arial", 12))
        self.status_label.pack(pady=10)

        self.id_btn = ttk.Button(self.root, text="Identifier le clavier (Appuyez sur une touche)", command=self.start_identification)
        self.id_btn.pack(pady=5)

        self.info_text = tk.Text(self.root, height=10, width=50)
        self.info_text.pack(pady=10)

        self.log("Logiciel démarré.")

    def log(self, msg):
        self.info_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.info_text.see(tk.END)

    def start_identification(self):
        self.target_handle = None
        self.mapping_active = False
        self.status_label.config(text="Statut : Identification en cours... Appuyez sur une touche.")
        self.log("En attente d'une touche pour identifier le clavier...")

    def start_threads(self):
        threading.Thread(target=self.raw_input_loop, daemon=True).start()
        threading.Thread(target=self.hook_loop, daemon=True).start()

    def raw_input_loop(self):
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                size = wintypes.UINT()
                user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                if size.value > 0:
                    buffer = ctypes.create_string_buffer(size.value)
                    user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, buffer, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                    raw = RAWINPUT.from_buffer(buffer)
                    if raw.header.dwType == RIM_TYPEKEYBOARD:
                        with self.lock:
                            # IMPORTANT: On 64-bit, hDevice is a large integer.
                            # We store its string representation or the raw value.
                            self.last_raw_event = {
                                "hDevice": raw.header.hDevice,
                                "vkey": raw.data.keyboard.VKey,
                                "time": time.time()
                            }
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        self.wnd_proc_ptr = WNDPROC(wnd_proc)

        class_name = "KeyboardRawInputWindow"
        class WNDCLASSEX(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON), ("hCursor", wintypes.HCURSOR), ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]

        wc = WNDCLASSEX()
        wc.cbSize = ctypes.sizeof(WNDCLASSEX); wc.lpfnWndProc = self.wnd_proc_ptr; wc.hInstance = kernel32.GetModuleHandleW(None); wc.lpszClassName = class_name
        user32.RegisterClassExW(ctypes.byref(wc))
        hwnd = user32.CreateWindowExW(0, class_name, "HiddenRawInput", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)

        rid = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd)
        user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def hook_loop(self):
        def hook_callback(nCode, wParam, lParam):
            if nCode >= 0:
                kb = KBDLLHOOKSTRUCT.from_address(lParam)
                if kb.flags & 0x10: # Ignore injected
                    return user32.CallNextHookEx(None, nCode, wParam, lParam)

                with self.lock:
                    current = self.last_raw_event.copy()

                # Match based on time and VKey
                if current["vkey"] == kb.vkCode and (time.time() - current["time"]) < 0.05:
                    # Identification
                    if self.target_handle is None:
                        self.target_handle = current["hDevice"]
                        self.mapping_active = True
                        self.root.after(0, lambda: self.log(f"Clavier Cible Identifié : {self.target_handle}"))
                        self.root.after(0, lambda: self.status_label.config(text=f"Statut : Actif (Clavier {self.target_handle})"))

                    # Remapping
                    elif self.mapping_active and current["hDevice"] == self.target_handle:
                        if kb.vkCode in self.mapping:
                            if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
                                self.root.after(0, lambda v=kb.vkCode: self.log(f"Remap: {hex(v)} -> {hex(self.mapping[v])}"))
                                self.press_key(self.mapping[kb.vkCode])
                            return 1 # Block

            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        self.hook_proc_ptr = HOOKPROC(hook_callback)
        self.hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.hook_proc_ptr, kernel32.GetModuleHandleW(None), 0)

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def press_key(self, vk):
        inputs = (INPUT * 2)()
        inputs[0].type = 1
        inputs[0].u.ki.wVk = vk
        inputs[0].u.ki.dwFlags = 0
        inputs[1].type = 1
        inputs[1].u.ki.wVk = vk
        inputs[1].u.ki.dwFlags = 2
        user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))

if __name__ == "__main__":
    if sys.platform != "win32":
        print("Windows requis.")
    else:
        root = tk.Tk()
        app = KeyboardApp(root)
        root.mainloop()
