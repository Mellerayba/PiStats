"""
Minimal BLE peripheral hello-world. Proves bluezero can advertise a
GATT service and that a central (bleak, on the Mac) can discover,
connect, and read from it — before building the real state/command
protocol on top of BLE.

Requires:
    sudo apt install -y python3-dbus python3-gi
    sudo pip3 install --break-system-packages bluezero

Run on the Pi with:
    sudo python3 ble_hello_peripheral.py
(sudo is needed — BlueZ's GATT manager D-Bus API requires root for
registering a peripheral application under the default Raspberry Pi
OS D-Bus policy.)
"""
from bluezero import peripheral

ADAPTER_ADDRESS = "B8:27:EB:66:78:BB"  # this Pi's onboard Bluetooth adapter
SERVICE_UUID = "12345678-1234-5678-1234-56789abc0000"
HELLO_CHAR_UUID = "12345678-1234-5678-1234-56789abc0001"


def read_hello():
    return list(b"hello from the pi")


def main():
    ble_peripheral = peripheral.Peripheral(ADAPTER_ADDRESS, local_name="PiStats")
    ble_peripheral.add_service(srv_id=1, uuid=SERVICE_UUID, primary=True)
    ble_peripheral.add_characteristic(
        srv_id=1,
        chr_id=1,
        uuid=HELLO_CHAR_UUID,
        value=list(b"hello from the pi"),
        notifying=False,
        flags=["read"],
        read_callback=read_hello,
    )
    # This adapter's legacy advertising payload is capped at 31 bytes
    # (MaxAdvLen from `bluetoothctl show`). Our 128-bit service UUID
    # alone eats 18 of those, which combined with flags + local name
    # overflows it (BlueZ then rejects the whole advertisement with a
    # generic "Failed"/"Invalid Parameters" error). The GATT service is
    # still registered as primary either way — this just keeps its UUID
    # out of the advertisement itself; a central finds us by local name
    # and discovers services normally after connecting.
    ble_peripheral.primary_services = []

    print("Advertising as 'PiStats'...")
    ble_peripheral.publish()


if __name__ == "__main__":
    main()
