import ctypes
from ctypes import wintypes
import sys

# Windows Constants
RID_INPUT = 0x10000003
RID_HEADER = 0x10000005

RIDI_DEVICENAME = 0x20000007
RIDI_DEVICEINFO = 0x2000000b

RIM_TYPEMOUSE = 0
RIM_TYPEKEYBOARD = 1
RIM_TYPEHID = 2

class RID_DEVICE_INFO_KEYBOARD(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSubType", wintypes.DWORD),
        ("dwKeyboardMode", wintypes.DWORD),
        ("dwNumberOfFunctionKeys", wintypes.DWORD),
        ("dwNumberOfIndicators", wintypes.DWORD),
        ("dwNumberOfKeysTotal", wintypes.DWORD),
    ]

class RID_DEVICE_INFO_MOUSE(ctypes.Structure):
    _fields_ = [
        ("dwId", wintypes.DWORD),
        ("dwNumberOfButtons", wintypes.DWORD),
        ("dwSampleRate", wintypes.DWORD),
        ("fHasHorizontalWheel", wintypes.BOOL),
    ]

class RID_DEVICE_INFO_HID(ctypes.Structure):
    _fields_ = [
        ("dwVendorId", wintypes.DWORD),
        ("dwProductId", wintypes.DWORD),
        ("dwVersionNumber", wintypes.DWORD),
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
    ]

class RID_DEVICE_INFO_UNION(ctypes.Union):
    _fields_ = [
        ("mouse", RID_DEVICE_INFO_MOUSE),
        ("keyboard", RID_DEVICE_INFO_KEYBOARD),
        ("hid", RID_DEVICE_INFO_HID),
    ]

class RID_DEVICE_INFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("dwType", wintypes.DWORD),
        ("u", RID_DEVICE_INFO_UNION),
    ]

class RAWINPUTDEVICELIST(ctypes.Structure):
    _fields_ = [
        ("hDevice", wintypes.HANDLE),
        ("dwType", wintypes.DWORD),
    ]

def list_keyboards():
    if sys.platform != "win32":
        print("This script only works on Windows.")
        return []

    user32 = ctypes.windll.user32

    # Setup argtypes/restypes for 64-bit safety
    user32.GetRawInputDeviceList.argtypes = [ctypes.POINTER(RAWINPUTDEVICELIST), ctypes.POINTER(wintypes.UINT), wintypes.UINT]
    user32.GetRawInputDeviceList.restype = wintypes.UINT

    user32.GetRawInputDeviceInfoW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID, ctypes.POINTER(wintypes.UINT)]
    user32.GetRawInputDeviceInfoW.restype = wintypes.UINT

    # Get number of devices
    n_devices = wintypes.UINT()
    user32.GetRawInputDeviceList(None, ctypes.byref(n_devices), ctypes.sizeof(RAWINPUTDEVICELIST))

    # Get device list
    device_list = (RAWINPUTDEVICELIST * n_devices.value)()
    user32.GetRawInputDeviceList(device_list, ctypes.byref(n_devices), ctypes.sizeof(RAWINPUTDEVICELIST))

    keyboards = []
    for i in range(n_devices.value):
        if device_list[i].dwType == RIM_TYPEKEYBOARD:
            h_device = device_list[i].hDevice

            # Get device name
            name_size = wintypes.UINT()
            user32.GetRawInputDeviceInfoW(h_device, RIDI_DEVICENAME, None, ctypes.byref(name_size))
            name_buffer = ctypes.create_unicode_buffer(name_size.value)
            user32.GetRawInputDeviceInfoW(h_device, RIDI_DEVICENAME, name_buffer, ctypes.byref(name_size))

            # Get device info
            info = RID_DEVICE_INFO()
            info.cbSize = ctypes.sizeof(RID_DEVICE_INFO)
            info_size = wintypes.UINT(info.cbSize)
            user32.GetRawInputDeviceInfoW(h_device, RIDI_DEVICEINFO, ctypes.byref(info), ctypes.byref(info_size))

            kb_info = {
                "handle": h_device,
                "name": name_buffer.value,
                "type": "Keyboard",
                "vid": None,
                "pid": None
            }

            # Try to extract VID/PID from name if it's a HID-like name or if it's stored in HID info
            # Actually, for RIM_TYPEKEYBOARD, sometimes the HID info isn't populated as HID but as Keyboard.
            # But the name often contains VID/PID string.

            keyboards.append(kb_info)

    return keyboards

if __name__ == "__main__":
    kbds = list_keyboards()
    print(f"Found {len(kbds)} keyboards:")
    for k in kbds:
        print(f"Handle: {k['handle']}, Name: {k['name']}")
