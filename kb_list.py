import ctypes
from ctypes import wintypes
import sys

# Windows Constants
RID_INPUT = 0x10000003
RIDI_DEVICENAME = 0x20000007
RIDI_DEVICEINFO = 0x2000000b
RIM_TYPEKEYBOARD = 1

class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [("hDevice", wintypes.HANDLE), ("dwType", wintypes.DWORD)]

user32 = ctypes.windll.user32
user32.GetRawInputDeviceList.argtypes = [ctypes.POINTER(RAWINPUTDEVICELIST), ctypes.POINTER(wintypes.UINT), wintypes.UINT]
user32.GetRawInputDeviceList.restype = wintypes.UINT
user32.GetRawInputDeviceInfoW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, ctypes.POINTER(wintypes.UINT)]
user32.GetRawInputDeviceInfoW.restype = wintypes.UINT

def list_keyboards():
    if sys.platform != "win32":
        return []

    n_devices = wintypes.UINT()
    user32.GetRawInputDeviceList(None, ctypes.byref(n_devices), ctypes.sizeof(RAWINPUTDEVICELIST))

    device_list = (RAWINPUTDEVICELIST * n_devices.value)()
    user32.GetRawInputDeviceList(device_list, ctypes.byref(n_devices), ctypes.sizeof(RAWINPUTDEVICELIST))

    keyboards = []
    for i in range(n_devices.value):
        if device_list[i].dwType == RIM_TYPEKEYBOARD:
            h = device_list[i].hDevice
            name_size = wintypes.UINT()
            user32.GetRawInputDeviceInfoW(h, RIDI_DEVICENAME, None, ctypes.byref(name_size))
            name_buffer = ctypes.create_unicode_buffer(name_size.value)
            user32.GetRawInputDeviceInfoW(h, RIDI_DEVICENAME, name_buffer, ctypes.byref(name_size))
            keyboards.append({"handle": h, "name": name_buffer.value})
    return keyboards

if __name__ == "__main__":
    kbds = list_keyboards()
    print(f"Trouvé {len(kbds)} claviers :")
    for k in kbds:
        print(f"Handle: {k['handle']}, Name: {k['name']}")
