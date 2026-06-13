try:
    import hid
except ImportError:
    hid = None

import time

# Sayodevice constants
SAYO_VID = 0x8089

def find_sayodevices():
    if not hid:
        print("Erreur : La bibliothèque 'hidapi' n'est pas installée ou 'hidapi.dll' est manquante.")
        return []

    devices = []
    try:
        for d in hid.enumerate():
            if d['vendor_id'] == SAYO_VID:
                devices.append(d)
    except Exception as e:
        print(f"Erreur lors de l'énumération HID : {e}")
    return devices

def set_rgb_simple(device_path, r, g, b):
    if not hid: return
    try:
        h = hid.device()
        h.open_path(device_path)

        # Structure de rapport générique (64 octets)
        report = [0] * 64
        report[0] = 0x00
        report[1] = 0x01 # Commande LED (Exemple)
        report[2] = r
        report[3] = g
        report[4] = b

        # h.write(report)
        print(f"Envoi RGB {r},{g},{b} vers {device_path}")
        h.close()
    except Exception as e:
        print(f"Erreur HID : {e}")

if __name__ == "__main__":
    if not hid:
        print("Veuillez installer hidapi : pip install hidapi")
        print("Et assurez-vous que hidapi.dll (64-bit) est présent.")
    else:
        devs = find_sayodevices()
        if not devs:
            print("Aucun Sayodevice trouvé.")
        for d in devs:
            print(f"Trouvé : {d['product_string']} (PID: {hex(d['product_id'])})")
