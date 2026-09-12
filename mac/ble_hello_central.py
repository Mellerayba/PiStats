"""
Minimal BLE central hello-world. Pairs with
pi/ble_hello_peripheral.py to prove bleak can discover, connect to,
and read from the Pi's BLE peripheral before building the real
state/command protocol on top of BLE.

Requires: pip3 install bleak

Run on the Mac with:
    python3 ble_hello_central.py
"""
import asyncio

from bleak import BleakClient, BleakScanner

HELLO_CHAR_UUID = "12345678-1234-5678-1234-56789abc0001"
DEVICE_NAME = "PiStats"


async def main():
    print(f"Scanning for {DEVICE_NAME}...")
    device = await BleakScanner.find_device_by_name(DEVICE_NAME, timeout=15)
    if device is None:
        print("Device not found. Is ble_hello_peripheral.py running on the Pi?")
        return

    print("Found:", device.address)
    async with BleakClient(device) as client:
        print("Connected:", client.is_connected)
        value = await client.read_gatt_char(HELLO_CHAR_UUID)
        print("Read value:", value.decode())


if __name__ == "__main__":
    asyncio.run(main())
