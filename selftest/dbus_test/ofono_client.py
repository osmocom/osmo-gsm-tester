#!/usr/bin/env python3

'''
Power on and off some modem on ofono, while running the glib main loop in a
thread and receiving modem state changes by dbus signals.
'''

from pydbus import SystemBus, Variant
import time
import threading
import pprint

from gi.repository import GLib
loop = GLib.MainLoop()

def propchanged(*args, **kwargs):
        print('-> PROP CHANGED: %r %r' % (args, kwargs))

class GlibMainloop(threading.Thread):
        def run(self):
                loop.run()

ml = GlibMainloop()
ml.start()

try:
        bus = SystemBus()

        print('\n- list modems')
        root = bus.get("org.ofono", '/')
        print(root.Introspect())
	modems = sorted(root.GetModems())
        pprint.pprint(modems)

        first_modem_path = modems[0][0]
        print('\n- first modem %r' % first_modem_path)
        modem = bus.get("org.ofono", first_modem_path)
        modem.PropertyChanged.connect(propchanged)

        print(modem.Introspect())
        print(modem.GetProperties())

        print('\n- set Powered = True')
        modem.SetProperty('Powered', Variant('b', True))
        print('call returned')
        print(modem.GetProperties())

        time.sleep(1)

        print('\n- set Powered = False')
        modem.SetProperty('Powered', Variant('b', False))
        print('call returned')

        print(modem.GetProperties())
finally:
        loop.quit()
ml.join()
