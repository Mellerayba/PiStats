"""
Isolated test: registers a bare-minimum LE advertisement directly via
dbus-python (bypassing bluezero's Advertisement class entirely), to
check whether explicitly setting SecondaryChannel='1M' fixes the
"Invalid Parameters (0x0d)" failures we got from bluetoothctl/bluezero
on this Pi's old BCM43430A1 controller (which only supports legacy 1M
PHY, not 2M/Coded — BlueZ's default registration path seems to assume
otherwise for this chip).

Run on the Pi with:
    sudo python3 ble_adv_test.py
Ctrl+C to stop and unregister.
"""
import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

BLUEZ_SERVICE = "org.bluez"
LE_ADVERTISING_MANAGER_IFACE = "org.bluez.LEAdvertisingManager1"
LE_ADVERTISEMENT_IFACE = "org.bluez.LEAdvertisement1"
DBUS_PROP_IFACE = "org.freedesktop.DBus.Properties"
ADAPTER_PATH = "/org/bluez/hci0"


class Advertisement(dbus.service.Object):
    PATH = "/org/pistats/advertisement0"

    def __init__(self, bus):
        dbus.service.Object.__init__(self, bus, self.PATH)

    def get_properties(self):
        return {
            LE_ADVERTISEMENT_IFACE: {
                "Type": "peripheral",
                "LocalName": dbus.String("PiStats"),
                "SecondaryChannel": dbus.String("1M"),
            }
        }

    def get_path(self):
        return dbus.ObjectPath(self.PATH)

    @dbus.service.method(DBUS_PROP_IFACE, in_signature="s", out_signature="a{sv}")
    def GetAll(self, interface):
        if interface != LE_ADVERTISEMENT_IFACE:
            raise dbus.exceptions.DBusException(
                "org.bluez.Error.InvalidArguments", "Invalid interface"
            )
        return self.get_properties()[LE_ADVERTISEMENT_IFACE]

    @dbus.service.method(LE_ADVERTISEMENT_IFACE, in_signature="", out_signature="")
    def Release(self):
        print("Advertisement released")


def register_ok():
    print("Advertisement registered successfully!")


def register_err(error):
    print("Failed to register advertisement:", error)
    mainloop.quit()


dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
bus = dbus.SystemBus()
adapter_obj = bus.get_object(BLUEZ_SERVICE, ADAPTER_PATH)
ad_manager = dbus.Interface(adapter_obj, LE_ADVERTISING_MANAGER_IFACE)

advertisement = Advertisement(bus)
mainloop = GLib.MainLoop()

ad_manager.RegisterAdvertisement(
    advertisement.get_path(),
    {},
    reply_handler=register_ok,
    error_handler=register_err,
)

try:
    mainloop.run()
except KeyboardInterrupt:
    ad_manager.UnregisterAdvertisement(advertisement.get_path())
