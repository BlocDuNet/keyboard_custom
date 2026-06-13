import ctypes
from ctypes import wintypes
import threading
import time
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os

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

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON), ("hCursor", wintypes.HCURSOR), ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)
    ]

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
CONFIG_FILE = "kb_config.json"

class KeyboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Keyboard Customizer PRO (DEBUG)")
        self.root.geometry("900x650")

        self.last_raw_event = {"hDevice": None, "vk": 0, "time": 0}
        self.lock = threading.Lock()

        self.is_identifying = False
        self.config = self.load_config()

        self.setup_ui()
        self.start_threads()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except: pass
        return {"keyboards": {}}

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def setup_ui(self):
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # Left: Device List
        self.left_frame = ttk.Frame(self.paned, padding="10")
        self.paned.add(self.left_frame, weight=1)
        ttk.Label(self.left_frame, text="Dispositifs", font=("Arial", 11, "bold")).pack()
        self.kb_tree = ttk.Treeview(self.left_frame, columns=("ID", "Nom"), show="headings", height=8)
        self.kb_tree.heading("ID", text="ID"); self.kb_tree.heading("Nom", text="Nom")
        self.kb_tree.column("ID", width=80); self.kb_tree.column("Nom", width=120)
        self.kb_tree.pack(fill=tk.BOTH, expand=True)
        self.kb_tree.bind("<<TreeviewSelect>>", self.on_kb_select)

        btn_box = ttk.Frame(self.left_frame); btn_box.pack(fill=tk.X, pady=5)
        ttk.Button(btn_box, text="IDENTIFIER", command=self.start_identification).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="Renommer", command=self.rename_keyboard).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="X", width=3, command=self.delete_keyboard).pack(side=tk.LEFT, padx=2)

        # Right: Config & Logs
        self.right_frame = ttk.Frame(self.paned, padding="10")
        self.paned.add(self.right_frame, weight=2)

        # Config Frame
        self.cfg_frame = ttk.LabelFrame(self.right_frame, text="Configuration des touches", padding="10")
        self.cfg_frame.pack(fill=tk.X, pady=5)

        self.sel_label = ttk.Label(self.cfg_frame, text="Sélectionnez un clavier à gauche", font=("Arial", 9, "italic"))
        self.sel_label.pack(pady=5)

        map_input = ttk.Frame(self.cfg_frame)
        map_input.pack(fill=tk.X)
        ttk.Label(map_input, text="De (Hex):").grid(row=0, column=0)
        self.vk_from = ttk.Entry(map_input, width=8); self.vk_from.grid(row=0, column=1, padx=5)
        ttk.Label(map_input, text="Vers (Hex):").grid(row=0, column=2)
        self.vk_to = ttk.Entry(map_input, width=8); self.vk_to.grid(row=0, column=3, padx=5)
        ttk.Button(map_input, text="Ajouter", command=self.add_mapping).grid(row=0, column=4, padx=5)

        self.mapping_list = tk.Listbox(self.cfg_frame, height=4)
        self.mapping_list.pack(fill=tk.X, pady=5)
        ttk.Button(self.cfg_frame, text="Supprimer Mapping", command=self.delete_mapping).pack(anchor=tk.E)

        # Logs
        ttk.Label(self.right_frame, text="Journal Système & Debug :").pack(anchor=tk.W, pady=(10,0))
        self.log_widget = tk.Text(self.right_frame, height=15, width=60, font=("Consolas", 8))
        self.log_widget.pack(fill=tk.BOTH, expand=True)
        self.log_widget.tag_config("raw", foreground="gray")
        self.log_widget.tag_config("hook", foreground="purple")
        self.log_widget.tag_config("match", foreground="green", font=("Consolas", 8, "bold"))
        self.log_widget.tag_config("err", foreground="red")

        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.refresh_kb_list()

    def log(self, msg, tag=None):
        self.log_widget.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n", tag)
        self.log_widget.see(tk.END)

    def refresh_kb_list(self):
        for i in self.kb_tree.get_children(): self.kb_tree.delete(i)
        for h, info in self.config["keyboards"].items():
            self.kb_tree.insert("", tk.END, values=(h, info["name"]))

    def on_kb_select(self, e):
        sel = self.kb_tree.selection()
        if not sel: return
        h = str(self.kb_tree.item(sel[0])["values"][0])
        info = self.config["keyboards"].get(h)
        if info:
            self.sel_label.config(text=f"Cible: {info['name']} ({h})", font=("Arial", 9, "bold"))
            self.refresh_mapping_list(h)

    def refresh_mapping_list(self, h):
        self.mapping_list.delete(0, tk.END)
        mappings = self.config["keyboards"][h].get("mappings", {})
        for f, t in mappings.items(): self.mapping_list.insert(tk.END, f"{f} -> {t}")

    def add_mapping(self):
        sel = self.kb_tree.selection()
        if not sel: return
        h = str(self.kb_tree.item(sel[0])["values"][0])
        f, t = self.vk_from.get().strip(), self.vk_to.get().strip()
        if f and t:
            self.config["keyboards"][h].setdefault("mappings", {})[f] = t
            self.save_config(); self.refresh_mapping_list(h)

    def delete_mapping(self):
        sel_kb = self.kb_tree.selection()
        sel_map = self.mapping_list.curselection()
        if not sel_kb or not sel_map: return
        h = str(self.kb_tree.item(sel_kb[0])["values"][0])
        map_text = self.mapping_list.get(sel_map[0])
        f = map_text.split(" -> ")[0]
        if f in self.config["keyboards"][h]["mappings"]:
            del self.config["keyboards"][h]["mappings"][f]
            self.save_config(); self.refresh_mapping_list(h)

    def start_identification(self):
        self.is_identifying = True
        self.log(">>> MODE IDENTIFICATION ACTIF. Appuyez sur une touche.", "match")

    def rename_keyboard(self):
        sel = self.kb_tree.selection()
        if not sel: return
        h = str(self.kb_tree.item(sel[0])["values"][0])
        name = simpledialog.askstring("Nom", "Nouveau nom :")
        if name: self.config["keyboards"][h]["name"] = name; self.save_config(); self.refresh_kb_list()

    def delete_keyboard(self):
        sel = self.kb_tree.selection()
        if not sel: return
        h = str(self.kb_tree.item(sel[0])["values"][0])
        del self.config["keyboards"][h]; self.save_config(); self.refresh_kb_list()

    def start_threads(self):
        threading.Thread(target=self.raw_input_loop, daemon=True).start()
        threading.Thread(target=self.hook_loop, daemon=True).start()

    def raw_input_loop(self):
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                size = wintypes.UINT()
                user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                if size.value > 0:
                    buffer = ctypes.create_string_buffer(size.value)
                    user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, buffer, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                    raw = RAWINPUT.from_buffer(buffer)
                    if raw.header.dwType == RIM_TYPEKEYBOARD:
                        with self.lock: self.last_raw_event = {"hDevice": raw.header.hDevice, "vk": raw.data.keyboard.VKey, "time": time.time()}
                        self.root.after(0, lambda: self.log(f"RAW: Dev={raw.header.hDevice} VK={hex(raw.data.keyboard.VKey)}", "raw"))
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wnd_proc = WNDPROC(wnd_proc)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = self._wnd_proc
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "KBC_RawInput"
        user32.RegisterClassExW(ctypes.byref(wc))
        hwnd = user32.CreateWindowExW(0, wc.lpszClassName, None, 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
        rid = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd)
        if user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid)):
            self.root.after(0, lambda: self.log("Raw Input enregistré.", "match"))

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))

    def hook_loop(self):
        def hook_callback(nCode, wParam, lParam):
            if nCode >= 0:
                kb = KBDLLHOOKSTRUCT.from_address(lParam)
                if kb.flags & 0x10: return user32.CallNextHookEx(None, nCode, wParam, lParam)
                with self.lock: current = self.last_raw_event.copy()
                self.root.after(0, lambda: self.log(f"HOOK: VK={hex(kb.vkCode)}", "hook"))

                if current["vk"] == kb.vkCode and (time.time() - current["time"]) < 0.2:
                    h_str = str(current["hDevice"])
                    if self.is_identifying:
                        self.is_identifying = False
                        if h_str not in self.config["keyboards"]:
                            self.config["keyboards"][h_str] = {"name": f"Kbd_{h_str[-4:]}", "mappings": {}}
                        self.save_config(); self.root.after(0, self.refresh_kb_list)
                        self.root.after(0, lambda: self.log(f"IDENTIFIE: {h_str}", "match"))
                        return 0

                    if h_str in self.config["keyboards"]:
                        maps = self.config["keyboards"][h_str].get("mappings", {})
                        vk_hex = hex(kb.vkCode).lower().replace("0x0", "0x") if kb.vkCode < 16 else hex(kb.vkCode).lower()
                        # Fallback simple check
                        vk_hex_alt = hex(kb.vkCode)
                        vk_match = maps.get(vk_hex) or maps.get(vk_hex_alt) or maps.get(vk_hex.upper())

                        if vk_match and (wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN):
                            try:
                                self.press_key(int(vk_match, 16))
                                self.root.after(0, lambda: self.log(f"REMAP: {vk_hex}->{vk_match}", "match"))
                                return 1
                            except: pass

            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        self._hook_proc = HOOKPROC(hook_callback)
        self.hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, kernel32.GetModuleHandleW(None), 0)
        if self.hook_id: self.root.after(0, lambda: self.log("Hook installé.", "match"))
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))

    def press_key(self, vk):
        inputs = (INPUT * 2)()
        for i in range(2): inputs[i].type = 1; inputs[i].u.ki.wVk = vk
        inputs[1].u.ki.dwFlags = 2
        user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))

    def on_exit(self):
        if hasattr(self, 'hook_id') and self.hook_id: user32.UnhookWindowsHookEx(self.hook_id)
        self.root.destroy()

if __name__ == "__main__":
    if sys.platform == "win32":
        root = tk.Tk(); app = KeyboardApp(root); root.mainloop()
