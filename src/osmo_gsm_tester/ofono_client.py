# osmo_gsm_tester: DBUS client to talk to ofono
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from . import log

from pydbus import SystemBus, Variant
import time
import pprint

from gi.repository import GLib
glib_main_loop = GLib.MainLoop()
glib_main_ctx = glib_main_loop.get_context()
bus = SystemBus()

def poll():
    global glib_main_ctx
    while glib_main_ctx.pending():
        glib_main_ctx.iteration()

def get(path):
    global bus
    return bus.get('org.ofono', path)

def list_modems():
    root = get('/')
    return sorted(root.GetModems())


class Modem(log.Origin):
    'convenience for ofono Modem interaction'
    msisdn = None

    def __init__(self, conf):
        self.conf = conf
        self.path = conf.get('path')
        self.set_name(self.path)
        self.set_log_category(log.C_BUS)
        self._dbus_obj = None
        self._interfaces_was = set()
        poll()

    def set_msisdn(self, msisdn):
        self.msisdn = msisdn

    def imsi(self):
        return self.conf.get('imsi')

    def ki(self):
        return self.conf.get('ki')

    def set_powered(self, on=True):
        self.dbus_obj.SetProperty('Powered', Variant('b', on))

    def dbus_obj(self):
        if self._dbus_obj is not None:
            return self._dbus_obj
        self._dbus_obj = get(self.path)
        self._dbus_obj.PropertyChanged.connect(self._on_property_change)
        self._on_interfaces_change(self.properties().get('Interfaces'))

    def properties(self):
        return self.dbus_obj().GetProperties()

    def _on_property_change(self, name, value):
        if name == 'Interfaces':
            self._on_interfaces_change(value)

    def _on_interfaces_change(self, interfaces_now):
        now = set(interfaces_now)
        additions = now - self._interfaces_was
        removals = self._interfaces_was - now
        self._interfaces_was = now
        for iface in removals:
            with log.Origin('modem.disable(%s)' % iface):
                try:
                    self._on_interface_disabled(iface)
                except:
                    self.log_exn()
        for iface in additions:
            with log.Origin('modem.enable(%s)' % iface):
                try:
                    self._on_interface_enabled(iface)
                except:
                    self.log_exn()

    def _on_interface_enabled(self, interface_name):
        self.dbg('Interface enabled:', interface_name)
        # todo: when the messages service comes up, connect a message reception signal

    def _on_interface_disabled(self, interface_name):
        self.dbg('Interface disabled:', interface_name)

    def connect(self, nitb):
        'set the modem up to connect to MCC+MNC from NITB config'
        self.log('connect to', nitb)
        self.err('Modem.connect() is still a fake and does not do anything')

    def sms_send(self, msisdn):
        self.log('send sms to MSISDN', msisdn)
        self.err('Modem.sms_send() is still a fake and does not do anything')
        return 'todo'

# vim: expandtab tabstop=4 shiftwidth=4
