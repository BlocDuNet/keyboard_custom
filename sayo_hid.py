import hid
import time

# Sayodevice constants
SAYO_VID = 0x8089
# Common PIDs found in research, might vary by model (O3C, etc.)
# PID might be 0x0001, 0x0002, etc.

def find_sayodevices():
    devices = []
    for d in hid.enumerate():
        if d['vendor_id'] == SAYO_VID:
            devices.append(d)
    return devices

def set_rgb_simple(device_path, r, g, b):
    try:
        h = hid.device()
        h.open_path(device_path)

        # This is a placeholder report based on common HID keyboard RGB protocols
        # Actual Sayodevice protocol might differ (e.g., 64-byte report starting with a specific byte)
        # Based on research, Sayodevice often uses a report ID 0 or 1.

        # Most Sayodevices use 64-byte reports.
        report = [0] * 64
        report[0] = 0x00 # Report ID (if used by device)
        report[1] = 0x01 # Example command: Set LED?
        report[2] = r
        report[3] = g
        report[4] = b

        # h.write(report)
        print(f"Would send RGB {r},{g},{b} to {device_path}")
        h.close()
    except Exception as e:
        print(f"Error communicating with Sayodevice: {e}")

if __name__ == "__main__":
    devs = find_sayodevices()
    if not devs:
        print("No Sayodevice found.")
    for d in devs:
        print(f"Found: {d['product_string']} (PID: {hex(d['product_id'])}) at {d['path']}")
