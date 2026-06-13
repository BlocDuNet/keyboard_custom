import ctypes
from ctypes import wintypes
import threading
import time
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import json
import os
import queue
import subprocess

# --- Windows Constants ---
WM_INPUT = 0x00FF
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RIM_TYPEKEYBOARD = 1
WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105

# --- Windows Structures (Fixed for 64-bit) ---
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

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON), ("hCursor", wintypes.HCURSOR), ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)
    ]

# --- API Setup ---
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

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
user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT

# --- App Logic ---
CONFIG_FILE = "kb_config.json"

class KeyboardApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Keyboard Customizer PRO - v4.1 (Fixed Remapping)")
        self.root.geometry("1100x850")

        self.raw_events_buffer = []
        self.lock = threading.Lock()
        self.ui_queue = queue.Queue()

        self.is_identifying = False
        self.is_capturing = False
        self.capture_target = None

        self.config = self.load_config()

        self.setup_ui()
        self.start_threads()
        self.process_ui_tasks()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f: return json.load(f)
            except: pass
        return {"keyboards": {}}

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w') as f: json.dump(self.config, f, indent=4)
        except Exception as e: self.log(f"Erreur sauvegarde : {e}", "err")

    def setup_ui(self):
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        self.left_frame = ttk.Frame(self.paned, padding="10"); self.paned.add(self.left_frame, weight=1)
        ttk.Label(self.left_frame, text="Claviers Enregistrés", font=("Arial", 11, "bold")).pack(pady=5)
        self.kb_tree = ttk.Treeview(self.left_frame, columns=("ID", "Nom"), show="headings", height=10)
        self.kb_tree.heading("ID", text="ID"); self.kb_tree.heading("Nom", text="Nom")
        self.kb_tree.column("ID", width=100); self.kb_tree.column("Nom", width=150)
        self.kb_tree.pack(fill=tk.BOTH, expand=True)
        self.kb_tree.bind("<<TreeviewSelect>>", self.on_kb_select)

        btn_box = ttk.Frame(self.left_frame); btn_box.pack(fill=tk.X, pady=5)
        ttk.Button(btn_box, text="IDENTIFIER", command=self.start_identification).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="Renommer", command=self.rename_keyboard).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_box, text="Supprimer", command=self.delete_keyboard).pack(side=tk.LEFT, padx=2)

        self.right_frame = ttk.Frame(self.paned, padding="10"); self.paned.add(self.right_frame, weight=2)
        self.cfg_frame = ttk.LabelFrame(self.right_frame, text="Actions du Clavier", padding="10"); self.cfg_frame.pack(fill=tk.X, pady=5)
        self.sel_label = ttk.Label(self.cfg_frame, text="Sélectionnez un clavier", font=("Arial", 9, "bold")); self.sel_label.pack(pady=5)

        entry_frame = ttk.Frame(self.cfg_frame); entry_frame.pack(fill=tk.X, pady=5)
        ttk.Label(entry_frame, text="Touche :").grid(row=0, column=0)
        self.ent_from = ttk.Entry(entry_frame, width=12); self.ent_from.grid(row=0, column=1, padx=5)
        ttk.Button(entry_frame, text="Capturer", command=lambda: self.start_capture("from")).grid(row=0, column=2)

        ttk.Label(entry_frame, text="Action :").grid(row=1, column=0, pady=10)
        self.action_type = tk.StringVar(value="Key")
        ttk.Radiobutton(entry_frame, text="Remapper Touche", variable=self.action_type, value="Key").grid(row=1, column=1)
        ttk.Radiobutton(entry_frame, text="Lancer Script (.bat)", variable=self.action_type, value="Script").grid(row=1, column=2)

        ttk.Label(entry_frame, text="Valeur :").grid(row=2, column=0)
        self.ent_to = ttk.Entry(entry_frame, width=35); self.ent_to.grid(row=2, column=1, columnspan=2, sticky="ew", padx=5)
        ttk.Button(entry_frame, text="Parcourir...", command=self.browse_script).grid(row=2, column=3)
        ttk.Button(entry_frame, text="Capturer", command=lambda: self.start_capture("to")).grid(row=2, column=4)

        ttk.Button(self.cfg_frame, text="ENREGISTRER CETTE ACTION", command=self.add_mapping, style="Accent.TButton").pack(fill=tk.X, pady=10)

        self.mapping_list = tk.Listbox(self.cfg_frame, height=6, font=("Consolas", 10)); self.mapping_list.pack(fill=tk.X, pady=5)
        ttk.Button(self.cfg_frame, text="Supprimer sélection", command=self.delete_mapping).pack(anchor=tk.E)

        ttk.Label(self.right_frame, text="Journal Système :").pack(anchor=tk.W, pady=(10,0))
        self.log_widget = tk.Text(self.right_frame, height=15, width=60, font=("Consolas", 8)); self.log_widget.pack(fill=tk.BOTH, expand=True)
        self.log_widget.tag_config("match", foreground="green", font=("Consolas", 8, "bold")); self.log_widget.tag_config("err", foreground="red")

        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.refresh_kb_list()

    def browse_script(self):
        f = filedialog.askopenfilename(filetypes=[("Scripts BAT", "*.bat"), ("Tous les fichiers", "*.*")])
        if f: self.ent_to.delete(0, tk.END); self.ent_to.insert(0, f); self.action_type.set("Script")

    def log(self, msg, tag=None): self.ui_queue.put(("log", (msg, tag)))

    def process_ui_tasks(self):
        while not self.ui_queue.empty():
            task, data = self.ui_queue.get()
            if task == "log":
                msg, tag = data
                self.log_widget.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n", tag)
                self.log_widget.see(tk.END)
            elif task == "refresh_list": self.refresh_kb_list()
            elif task == "set_entry":
                field, val = data
                if field == "from": self.ent_from.delete(0, tk.END); self.ent_from.insert(0, val)
                else: self.ent_to.delete(0, tk.END); self.ent_to.insert(0, val)
        self.root.after(100, self.process_ui_tasks)

    def refresh_kb_list(self):
        for i in self.kb_tree.get_children(): self.kb_tree.delete(i)
        for h, info in self.config["keyboards"].items(): self.kb_tree.insert("", tk.END, values=(h, info["name"]))

    def on_kb_select(self, e):
        sel = self.kb_tree.selection()
        if not sel: return
        h = str(self.kb_tree.item(sel[0])["values"][0])
        info = self.config["keyboards"].get(h)
        if info: self.sel_label.config(text=f"Configuration : {info['name']} ({h})"); self.refresh_mapping_list(h)

    def refresh_mapping_list(self, h):
        self.mapping_list.delete(0, tk.END)
        mappings = self.config["keyboards"][h].get("mappings", {})
        for f, data in mappings.items(): self.mapping_list.insert(tk.END, f"{f} -> [{data.get('type')}] {data.get('value')}")

    def start_capture(self, target): self.is_capturing = True; self.capture_target = target; self.log(f"Capture en cours pour {target}...", "match")

    def add_mapping(self):
        sel = self.kb_tree.selection()
        if not sel: return
        h = str(self.kb_tree.item(sel[0])["values"][0])
        f, t_type, t_val = self.ent_from.get().strip().lower(), self.action_type.get(), self.ent_to.get().strip().lower()
        if f and t_val:
            if not f.startswith("0x"): f = "0x" + f
            if t_type == "Key" and not t_val.startswith("0x"): t_val = "0x" + t_val
            self.config["keyboards"][h].setdefault("mappings", {})[f] = {"type": t_type, "value": t_val}
            self.save_config(); self.refresh_mapping_list(h)

    def delete_mapping(self):
        sel_kb = self.kb_tree.selection()
        sel_map = self.mapping_list.curselection()
        if not (sel_kb and sel_map): return
        h = str(self.kb_tree.item(sel_kb[0])["values"][0])
        map_text = self.mapping_list.get(sel_map[0])
        f = map_text.split(" -> ")[0]
        if f in self.config["keyboards"][h].get("mappings", {}):
            del self.config["keyboards"][h]["mappings"][f]
            self.save_config(); self.refresh_mapping_list(h)

    def start_identification(self): with self.lock: self.is_identifying = True; self.log(">>> MODE IDENTIFICATION ACTIF. Pressez une touche.", "match")

    def rename_keyboard(self):
        sel = self.kb_tree.selection()
        if not sel: return
        h = str(self.kb_tree.item(sel[0])["values"][0])
        name = simpledialog.askstring("Nom", "Nom :")
        if name: self.config["keyboards"][h]["name"] = name; self.save_config(); self.refresh_kb_list()

    def delete_keyboard(self):
        sel = self.kb_tree.selection()
        if not sel: return
        h = str(self.kb_tree.item(sel[0])["values"][0])
        if messagebox.askyesno("Confirm", "Supprimer ?"): del self.config["keyboards"][h]; self.save_config(); self.refresh_kb_list()

    def start_threads(self):
        threading.Thread(target=self.raw_input_loop, daemon=True).start()
        threading.Thread(target=self.hook_loop, daemon=True).start()

    def raw_input_loop(self):
        WNDPROC_TYPE = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_INPUT:
                size = wintypes.UINT()
                user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                if size.value > 0:
                    buffer = ctypes.create_string_buffer(size.value)
                    user32.GetRawInputData(ctypes.cast(lparam, wintypes.HANDLE), RID_INPUT, buffer, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))
                    raw = RAWINPUT.from_buffer(buffer)
                    if raw.header.dwType == RIM_TYPEKEYBOARD:
                        h, vk, flags = raw.header.hDevice, raw.data.keyboard.VKey, raw.data.keyboard.Flags
                        is_down = not (flags & 0x01)
                        with self.lock:
                            self.raw_events_buffer.append({"h": h, "vk": vk, "time": time.time(), "is_down": is_down})
                            if len(self.raw_events_buffer) > 10: self.raw_events_buffer.pop(0)
                            if self.is_capturing and is_down: self.is_capturing = False; self.ui_queue.put(("set_entry", (self.capture_target, hex(vk))))
                            if self.is_identifying and is_down:
                                self.is_identifying = False; h_str = str(h)
                                if h_str not in self.config["keyboards"]: self.config["keyboards"][h_str] = {"name": f"Kbd_{h_str[-4:]}", "mappings": {}}
                                self.save_config(); self.ui_queue.put(("refresh_list", None)); self.log(f"ID SUCCESS: {h_str}", "match")
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)
        self._wnd_proc = WNDPROC_TYPE(wnd_proc); wc = WNDCLASSEXW(); wc.cbSize = ctypes.sizeof(WNDCLASSEXW); wc.lpfnWndProc = self._wnd_proc
        wc.hInstance = kernel32.GetModuleHandleW(None); wc.lpszClassName = f"KBC_RawInput_{int(time.time())}"
        user32.RegisterClassExW(ctypes.byref(wc)); hwnd = user32.CreateWindowExW(0, wc.lpszClassName, None, 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
        rid = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd); user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(rid))
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0: user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))

    def hook_loop(self):
        def hook_callback(nCode, wParam, lParam):
            if nCode >= 0:
                kb = KBDLLHOOKSTRUCT.from_address(lParam)
                if kb.flags & 0x10: return user32.CallNextHookEx(None, nCode, wParam, lParam)
                is_down_ev = (wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN)
                with self.lock:
                    match = None
                    for ev in reversed(self.raw_events_buffer):
                        if ev["vk"] == kb.vkCode and abs(time.time() - ev["time"]) < 0.2: match = ev; break
                if match:
                    h_str = str(match["h"])
                    if h_str in self.config["keyboards"]:
                        maps = self.config["keyboards"][h_str].get("mappings", {})
                        vk_hex = hex(kb.vkCode).lower()
                        m_data = maps.get(vk_hex) or maps.get(vk_hex.replace("0x", "0x0")) or maps.get(vk_hex.replace("0x0", "0x"))
                        if m_data:
                            m_type, m_val = m_data.get("type", "Key"), m_data.get("value")
                            if m_type == "Key":
                                self.press_key(int(m_val, 16), is_down=is_down_ev)
                                if is_down_ev: self.log(f"REMAP: {vk_hex} -> {m_val} (Dev {h_str})", "match")
                                return 1
                            elif m_type == "Script" and is_down_ev:
                                self.log(f"RUN: {m_val}", "match")
                                threading.Thread(target=lambda: subprocess.Popen(m_val, shell=True), daemon=True).start()
                                return 1
            return user32.CallNextHookEx(None, nCode, wParam, lParam)
        HOOKPROC_TYPE = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        self._hook_proc = HOOKPROC_TYPE(hook_callback)
        self.hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._hook_proc, kernel32.GetModuleHandleW(None), 0)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0: user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))

    def press_key(self, vk, is_down=True):
        inp = INPUT(); inp.type = 1
        inp.u.ki.wVk = vk; inp.u.ki.dwFlags = 0 if is_down else 2
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def on_exit(self):
        if hasattr(self, 'hook_id') and self.hook_id: user32.UnhookWindowsHookEx(self.hook_id)
        self.root.destroy()

if __name__ == "__main__":
    if sys.platform == "win32":
        root = tk.Tk(); app = KeyboardApp(root); root.mainloop()
