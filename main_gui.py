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
kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
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
        self.root.title("Keyboard Customizer PRO")
        self.root.geometry("600x500")

        self.last_raw_event = {"hDevice": None, "vkey": None, "time": 0}
        self.lock = threading.Lock()

        self.target_handle = None
        self.mapping_active = False
        self.is_identifying = False

        self.mapping = {0x41: 0x42} # A -> B

        self.setup_ui()
        self.start_threads()

    def setup_ui(self):
        # Header
        self.status_frame = ttk.Frame(self.root, padding="10")
        self.status_frame.pack(fill=tk.X)

        self.status_label = ttk.Label(self.status_frame, text="Statut : Prêt", font=("Arial", 11, "bold"))
        self.status_label.pack(side=tk.LEFT)

        self.target_label = ttk.Label(self.status_frame, text="Aucun clavier cible", foreground="gray")
        self.target_label.pack(side=tk.RIGHT)

        # Buttons
        self.btn_frame = ttk.Frame(self.root, padding="10")
        self.btn_frame.pack(fill=tk.X)

        self.id_btn = ttk.Button(self.btn_frame, text="Identifier le clavier", command=self.start_identification)
        self.id_btn.pack(side=tk.LEFT, padx=5)

        self.reset_btn = ttk.Button(self.btn_frame, text="Réinitialiser", command=self.reset_state)
        self.reset_btn.pack(side=tk.LEFT, padx=5)

        # Log
        self.log_frame = ttk.Frame(self.root, padding="10")
        self.log_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.log_frame, text="Journal des événements :").pack(anchor=tk.W)
        self.log_widget = tk.Text(self.log_frame, height=15, width=70, font=("Consolas", 9))
        self.log_widget.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self.log_widget, command=self.log_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_widget.config(yscrollcommand=scrollbar.set)

    def log(self, msg, color=None):
        timestamp = time.strftime('%H:%M:%S')
        self.log_widget.tag_config("red", foreground="red")
        self.log_widget.tag_config("blue", foreground="blue")
        self.log_widget.tag_config("green", foreground="green")

        tag = None
        if "Identification" in msg: tag = "blue"
        if "SUCCESS" in msg or "Actif" in msg: tag = "green"
        if "Erreur" in msg: tag = "red"

        self.log_widget.insert(tk.END, f"[{timestamp}] {msg}\n", tag)
        self.log_widget.see(tk.END)

    def reset_state(self):
        self.target_handle = None
        self.mapping_active = False
        self.is_identifying = False
        self.status_label.config(text="Statut : Prêt")
        self.target_label.config(text="Aucun clavier cible", foreground="gray")
        self.log("État réinitialisé.")

    def start_identification(self):
        self.is_identifying = True
        self.target_handle = None
        self.mapping_active = False
        self.status_label.config(text="Statut : Identification...")
        self.log("Mode Identification activé. Appuyez sur une touche sur le clavier souhaité.")

    def start_threads(self):
        # Thread for Raw Input
        t1 = threading.Thread(target=self.raw_input_loop, daemon=True)
        t1.start()
        # Thread for Keyboard Hook
        t2 = threading.Thread(target=self.hook_loop, daemon=True)
        t2.start()

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
                        h = raw.header.hDevice
                        vk = raw.data.keyboard.VKey
                        # Update shared state
                        with self.lock:
                            self.last_raw_event = {"hDevice": h, "vkey": vk, "time": time.time()}

                        # Monitor everything in log for debug
                        if not self.mapping_active or self.is_identifying:
                            # Use after to update GUI safely from thread
                            self.root.after(0, lambda h=h, vk=vk: self.log(f"Raw Input: Clavier {h} | Touche {hex(vk)}"))

            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        self.wnd_proc_ptr = WNDPROC(wnd_proc)

        class_name = "KeyboardApp_RawInput"
        class WNDCLASSEX(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON), ("hCursor", wintypes.HCURSOR), ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]

        wc = WNDCLASSEX()
        wc.cbSize = ctypes.sizeof(WNDCLASSEX); wc.lpfnWndProc = self.wnd_proc_ptr; wc.hInstance = kernel32.GetModuleHandleW(None); wc.lpszClassName = class_name
        user32.RegisterClassExW(ctypes.byref(wc))
        hwnd = user32.CreateWindowExW(0, class_name, "Hidden", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)

        rid = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd)
        if not user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)):
            self.root.after(0, lambda: messagebox.showerror("Erreur", "Impossible de s'enregistrer pour Raw Input."))
            return

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def hook_loop(self):
        def hook_callback(nCode, wParam, lParam):
            if nCode >= 0:
                kb = KBDLLHOOKSTRUCT.from_address(lParam)
                if kb.flags & 0x10: return user32.CallNextHookEx(None, nCode, wParam, lParam)

                with self.lock:
                    current = self.last_raw_event.copy()

                # Correlation Logic
                # Increase window to 100ms for safety
                if current["vkey"] == kb.vkCode and (time.time() - current["time"]) < 0.1:
                    # Identification Phase
                    if self.is_identifying:
                        self.target_handle = current["hDevice"]
                        self.is_identifying = False
                        self.mapping_active = True
                        self.root.after(0, self.on_identified)
                        return 0 # Allow this key to pass

                    # Mapping Phase
                    if self.mapping_active and current["hDevice"] == self.target_handle:
                        if kb.vkCode in self.mapping:
                            if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
                                self.root.after(0, lambda v=kb.vkCode: self.log(f"Mapping: {hex(v)} -> {hex(self.mapping[v])}"))
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

    def on_identified(self):
        self.status_label.config(text="Statut : ACTIF")
        self.target_label.config(text=f"Clavier Cible : {self.target_handle}", foreground="green")
        self.log(f"SUCCESS: Clavier {self.target_handle} identifie et active.")

    def press_key(self, vk):
        inputs = (INPUT * 2)()
        inputs[0].type = 1; inputs[0].u.ki.wVk = vk; inputs[0].u.ki.dwFlags = 0
        inputs[1].type = 1; inputs[1].u.ki.wVk = vk; inputs[1].u.ki.dwFlags = 2
        user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))

if __name__ == "__main__":
    if sys.platform != "win32":
        print("Erreur: Windows est requis.")
    else:
        root = tk.Tk()
        # Optional: ensure app runs as admin message?
        app = KeyboardApp(root)
        root.mainloop()
