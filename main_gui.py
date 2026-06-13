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
        self.root.title("Keyboard Customizer PRO")
        self.root.geometry("800x600")

        self.last_raw_event = {"hDevice": None, "vkey": None, "time": 0}
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
            except:
                pass
        return {"keyboards": {}} # { "handle_str": {"name": "...", "mappings": {"vk_from": vk_to}} }

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)

    def setup_ui(self):
        # Exit handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

        # Paned Window for split view
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # Left side: Keyboard List
        self.left_frame = ttk.Frame(self.paned, padding="10")
        self.paned.add(self.left_frame, weight=1)

        ttk.Label(self.left_frame, text="Claviers Enregistrés", font=("Arial", 11, "bold")).pack(pady=5)

        self.kb_tree = ttk.Treeview(self.left_frame, columns=("Handle", "Nom"), show="headings", height=10)
        self.kb_tree.heading("Handle", text="ID Matériel")
        self.kb_tree.heading("Nom", text="Nom Personnalisé")
        self.kb_tree.column("Handle", width=150)
        self.kb_tree.column("Nom", width=150)
        self.kb_tree.pack(fill=tk.BOTH, expand=True)
        self.kb_tree.bind("<<TreeviewSelect>>", self.on_kb_select)

        btn_grid = ttk.Frame(self.left_frame)
        btn_grid.pack(fill=tk.X, pady=5)

        ttk.Button(btn_grid, text="Identifier Nouveau", command=self.start_identification).grid(row=0, column=0, padx=2)
        ttk.Button(btn_grid, text="Renommer", command=self.rename_keyboard).grid(row=0, column=1, padx=2)
        ttk.Button(btn_grid, text="Supprimer", command=self.delete_keyboard).grid(row=0, column=2, padx=2)

        # Right side: Mappings and Log
        self.right_frame = ttk.Frame(self.paned, padding="10")
        self.paned.add(self.right_frame, weight=2)

        # Mapping section
        self.mapping_frame = ttk.LabelFrame(self.right_frame, text="Configuration des touches", padding="10")
        self.mapping_frame.pack(fill=tk.X, pady=5)

        self.sel_kb_label = ttk.Label(self.mapping_frame, text="Sélectionnez un clavier à gauche", font=("Arial", 9, "italic"))
        self.sel_kb_label.pack(pady=5)

        map_input_frame = ttk.Frame(self.mapping_frame)
        map_input_frame.pack(fill=tk.X)

        ttk.Label(map_input_frame, text="Touche Origine (Hex):").grid(row=0, column=0)
        self.vk_from_entry = ttk.Entry(map_input_frame, width=10)
        self.vk_from_entry.grid(row=0, column=1, padx=5)

        ttk.Label(map_input_frame, text="Touche Destination (Hex):").grid(row=0, column=2)
        self.vk_to_entry = ttk.Entry(map_input_frame, width=10)
        self.vk_to_entry.grid(row=0, column=3, padx=5)

        ttk.Button(map_input_frame, text="Ajouter/Modifier", command=self.add_mapping).grid(row=0, column=4, padx=5)

        self.mapping_list = tk.Listbox(self.mapping_frame, height=5)
        self.mapping_list.pack(fill=tk.X, pady=5)
        ttk.Button(self.mapping_frame, text="Supprimer Mapping", command=self.delete_mapping).pack(anchor=tk.E)

        # Log section
        ttk.Label(self.right_frame, text="Journal des événements :").pack(anchor=tk.W)
        self.log_widget = tk.Text(self.right_frame, height=10, width=50, font=("Consolas", 9))
        self.log_widget.pack(fill=tk.BOTH, expand=True)

        self.refresh_kb_list()

    def log(self, msg, tag=None):
        timestamp = time.strftime('%H:%M:%S')
        self.log_widget.tag_config("blue", foreground="blue")
        self.log_widget.tag_config("green", foreground="green")
        self.log_widget.insert(tk.END, f"[{timestamp}] {msg}\n", tag)
        self.log_widget.see(tk.END)

    def refresh_kb_list(self):
        for item in self.kb_tree.get_children():
            self.kb_tree.delete(item)
        for h_str, info in self.config["keyboards"].items():
            self.kb_tree.insert("", tk.END, values=(h_str, info["name"]))

    def on_kb_select(self, event):
        selected = self.kb_tree.selection()
        if not selected: return
        h_str = self.kb_tree.item(selected[0])["values"][0]
        h_str = str(h_str)
        info = self.config["keyboards"].get(h_str)
        if info:
            self.sel_kb_label.config(text=f"Clavier : {info['name']} ({h_str})", font=("Arial", 9, "bold"))
            self.refresh_mapping_list(h_str)

    def refresh_mapping_list(self, h_str):
        self.mapping_list.delete(0, tk.END)
        mappings = self.config["keyboards"][h_str].get("mappings", {})
        for vk_f, vk_t in mappings.items():
            self.mapping_list.insert(tk.END, f"{vk_f} -> {vk_t}")

    def start_identification(self):
        self.is_identifying = True
        messagebox.showinfo("Identification", "Appuyez sur une touche sur le clavier que vous voulez ajouter.")
        self.log("Mode Identification activé...", "blue")

    def rename_keyboard(self):
        selected = self.kb_tree.selection()
        if not selected: return
        h_str = str(self.kb_tree.item(selected[0])["values"][0])
        new_name = simpledialog.askstring("Renommer", "Nouveau nom pour ce clavier :")
        if new_name:
            self.config["keyboards"][h_str]["name"] = new_name
            self.save_config()
            self.refresh_kb_list()

    def delete_keyboard(self):
        selected = self.kb_tree.selection()
        if not selected: return
        h_str = str(self.kb_tree.item(selected[0])["values"][0])
        if messagebox.askyesno("Supprimer", "Voulez-vous supprimer ce clavier et ses réglages ?"):
            del self.config["keyboards"][h_str]
            self.save_config()
            self.refresh_kb_list()

    def add_mapping(self):
        selected = self.kb_tree.selection()
        if not selected: return
        h_str = str(self.kb_tree.item(selected[0])["values"][0])
        vk_f = self.vk_from_entry.get().strip()
        vk_t = self.vk_to_entry.get().strip()
        if vk_f and vk_t:
            if "mappings" not in self.config["keyboards"][h_str]:
                self.config["keyboards"][h_str]["mappings"] = {}
            self.config["keyboards"][h_str]["mappings"][vk_f] = vk_t
            self.save_config()
            self.refresh_mapping_list(h_str)

    def delete_mapping(self):
        selected_kb = self.kb_tree.selection()
        selected_map = self.mapping_list.curselection()
        if not selected_kb or not selected_map: return
        h_str = str(self.kb_tree.item(selected_kb[0])["values"][0])
        map_text = self.mapping_list.get(selected_map[0])
        vk_f = map_text.split(" -> ")[0]
        if vk_f in self.config["keyboards"][h_str]["mappings"]:
            del self.config["keyboards"][h_str]["mappings"][vk_f]
            self.save_config()
            self.refresh_mapping_list(h_str)

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
                            self.last_raw_event = {"hDevice": raw.header.hDevice, "vkey": raw.data.keyboard.VKey, "time": time.time()}
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        self.wnd_proc_ptr = WNDPROC(wnd_proc)
        class_name = "KBCustom_RawInput"
        class WNDCLASSEX(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.UINT), ("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON), ("hCursor", wintypes.HCURSOR), ("hbrBackground", wintypes.HBRUSH), ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR), ("hIconSm", wintypes.HICON)]
        wc = WNDCLASSEX(); wc.cbSize = ctypes.sizeof(WNDCLASSEX); wc.lpfnWndProc = self.wnd_proc_ptr; wc.hInstance = kernel32.GetModuleHandleW(None); wc.lpszClassName = class_name
        user32.RegisterClassExW(ctypes.byref(wc))
        hwnd = user32.CreateWindowExW(0, class_name, "Hidden", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None)
        rid = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd)
        user32.RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))

    def hook_loop(self):
        def hook_callback(nCode, wParam, lParam):
            if nCode >= 0:
                kb = KBDLLHOOKSTRUCT.from_address(lParam)
                if kb.flags & 0x10: return user32.CallNextHookEx(None, nCode, wParam, lParam)
                with self.lock: current = self.last_raw_event.copy()

                if current["vkey"] == kb.vkCode and (time.time() - current["time"]) < 0.1:
                    h_str = str(current["hDevice"])

                    if self.is_identifying:
                        self.is_identifying = False
                        if h_str not in self.config["keyboards"]:
                            self.config["keyboards"][h_str] = {"name": f"Clavier {h_str[-5:]}", "mappings": {}}
                        self.save_config()
                        self.root.after(0, self.refresh_kb_list)
                        self.root.after(0, lambda: self.log(f"Clavier {h_str} identifie!", "green"))
                        return 0

                    if h_str in self.config["keyboards"]:
                        mappings = self.config["keyboards"][h_str].get("mappings", {})
                        vk_hex = hex(kb.vkCode).upper().replace("0X", "0x")
                        # Try both lowercase and uppercase hex
                        vk_match = None
                        if vk_hex in mappings: vk_match = mappings[vk_hex]
                        elif vk_hex.lower() in mappings: vk_match = mappings[vk_hex.lower()]

                        if vk_match:
                            if wParam == WM_KEYDOWN or wParam == WM_SYSKEYDOWN:
                                try:
                                    target_vk = int(vk_match, 16)
                                    self.press_key(target_vk)
                                except: pass
                            return 1

            return user32.CallNextHookEx(None, nCode, wParam, lParam)

        HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        self.hook_proc_ptr = HOOKPROC(hook_callback)
        self.hook_id = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self.hook_proc_ptr, kernel32.GetModuleHandleW(None), 0)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) != 0:
            user32.TranslateMessage(ctypes.byref(msg)); user32.DispatchMessageW(ctypes.byref(msg))

    def press_key(self, vk):
        inputs = (INPUT * 2)()
        inputs[0].type = 1; inputs[0].u.ki.wVk = vk; inputs[0].u.ki.dwFlags = 0
        inputs[1].type = 1; inputs[1].u.ki.wVk = vk; inputs[1].u.ki.dwFlags = 2
        user32.SendInput(2, ctypes.byref(inputs), ctypes.sizeof(INPUT))

    def on_exit(self):
        if hasattr(self, 'hook_id'):
            user32.UnhookWindowsHookEx(self.hook_id)
        self.root.destroy()

if __name__ == "__main__":
    if sys.platform == "win32":
        root = tk.Tk()
        app = KeyboardApp(root)
        root.mainloop()
