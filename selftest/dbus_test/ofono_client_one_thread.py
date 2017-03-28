#!/usr/bin/env python3

'''
Power on and off some modem on ofono, while running the glib main loop in a
thread and receiving modem state changes by dbus signals.
'''

from pydbus import SystemBus, Variant
import time
import pprint

from gi.repository import GLib
glib_main_loop = GLib.MainLoop()
glib_main_ctx = glib_main_loop.get_context()

def propchanged(*args, **kwargs):
        print('-> PROP CHANGED: %r %r' % (args, kwargs))


def pump():
    global glib_main_ctx
    print('pump?')
    while glib_main_ctx.pending():
        print('* pump')
        glib_main_ctx.iteration()

def wait(condition):
    pump()
    while not condition():
        time.sleep(.1)
        pump()

bus = SystemBus()

print('\n- list modems')
root = bus.get("org.ofono", '/')
print(root.Introspect())
modems = sorted(root.GetModems())
pprint.pprint(modems)
pump()

first_modem_path = modems[0][0]
print('\n- first modem %r' % first_modem_path)
modem = bus.get("org.ofono", first_modem_path)
modem.PropertyChanged.connect(propchanged)

print(modem.Introspect())
print(modem.GetProperties())

print('\n- set Powered = True')
modem.SetProperty('Powered', Variant('b', True))
print('call returned')
print('- pump dbus events')
pump()
pump()
print('sleep 1')
time.sleep(1)
pump()


print('- modem properties:')
print(modem.GetProperties())


print('\n- set Powered = False')
modem.SetProperty('Powered', Variant('b', False))
print('call returned')

print(modem.GetProperties())

# vim: tabstop=4 shiftwidth=4 expandtab
