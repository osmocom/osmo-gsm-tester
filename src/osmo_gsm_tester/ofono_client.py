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

from . import log, test

from pydbus import SystemBus, Variant
import time
import pprint

from gi.repository import GLib
glib_main_loop = GLib.MainLoop()
glib_main_ctx = glib_main_loop.get_context()
bus = SystemBus()

I_NETREG = 'org.ofono.NetworkRegistration'
I_SMS = 'org.ofono.MessageManager'

def poll():
    global glib_main_ctx
    while glib_main_ctx.pending():
        glib_main_ctx.iteration()

def systembus_get(path):
    global bus
    return bus.get('org.ofono', path)

def list_modems():
    root = systembus_get('/')
    return sorted(root.GetModems())


class Modem(log.Origin):
    'convenience for ofono Modem interaction'
    msisdn = None
    sms_received_list = None

    def __init__(self, conf):
        self.conf = conf
        self.path = conf.get('path')
        self.set_name(self.path)
        self.set_log_category(log.C_BUS)
        self._dbus_obj = None
        self._interfaces = set()
        self.sms_received_list = []
        test.poll()

    def set_msisdn(self, msisdn):
        self.msisdn = msisdn

    def imsi(self):
        imsi = self.conf.get('imsi')
        if not imsi:
            with self:
                raise RuntimeError('No IMSI')
        return imsi

    def ki(self):
        return self.conf.get('ki')

    def _dbus_set_bool(self, name, bool_val):
        # to make sure any pending signals are received before we send out more DBus requests
        test.poll()

        val = bool(bool_val)
        self.log('Setting', name, val)
        self.dbus_obj().SetProperty(name, Variant('b', val))

        test.wait(self.property_is, name, bool_val)

    def property_is(self, name, val):
        is_val = self.properties().get(name)
        self.dbg(name, '==', is_val)
        return is_val is not None and is_val == val

    def set_powered(self, on=True):
        self._dbus_set_bool('Powered', on)

    def set_online(self, on=True):
        self._dbus_set_bool('Online', on)

    def dbus_obj(self):
        if self._dbus_obj is not None:
            return self._dbus_obj
        self._dbus_obj = systembus_get(self.path)
        self._dbus_obj.PropertyChanged.connect(self._on_property_change)
        self._on_interfaces_change(self.properties().get('Interfaces'))
        return self._dbus_obj

    def properties(self):
        return self.dbus_obj().GetProperties()

    def _on_property_change(self, name, value):
        if name == 'Interfaces':
            self._on_interfaces_change(value)

    def _on_interfaces_change(self, interfaces_now):
        now = set(interfaces_now)
        additions = now - self._interfaces
        removals = self._interfaces - now
        self._interfaces = now
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

    def _interface_really_present(self, interface_name):
        try:
            self.dbus_obj()[interface_name]
            return True
        except:
            return False

    def _on_interface_enabled(self, interface_name):
        self.dbg('Interface enabled:', interface_name)
        test.wait(self._interface_really_present, interface_name)
        if interface_name == I_SMS:
            self.dbus_obj()[I_SMS].IncomingMessage.connect(self._on_incoming_message)

    def _on_interface_disabled(self, interface_name):
        self.dbg('Interface disabled:', interface_name)

    def has_interface(self, name):
        return name in self._interfaces

    def connect(self, nitb):
        'set the modem up to connect to MCC+MNC from NITB config'
        self.log('connect to', nitb)
        self.set_powered(False)
        self.set_powered()
        self.set_online(False)
        self.set_online()
        if not self.has_interface(I_NETREG):
            self.log('No %r interface, hoping that the modem connects by itself' % I_NETREG)
        else:
            self.log('Use of %r interface not implemented yet, hoping that the modem connects by itself' % I_NETREG)

    def sms_send(self, to_msisdn):
        if hasattr(to_msisdn, 'msisdn'):
            to_msisdn = to_msisdn.msisdn
        sms = Sms(self.msisdn, to_msisdn)
        self.log('sending sms to MSISDN', to_msisdn, sms=sms)
        if not self.has_interface(I_SMS):
            raise RuntimeError('Modem cannot send SMS, interface not active: %r' % I_SMS)
        mm = self.dbus_obj()[I_SMS]
        mm.SendMessage(to_msisdn, str(sms))
        return sms

    def _on_incoming_message(self, message, info):
        self.log('Incoming SMS:', repr(message), info=info)
        self.sms_received_list.append((message, info))

    def sms_was_received(self, sms):
        for msg, info in self.sms_received_list:
            if sms.matches(msg):
                self.log('SMS received as expected:', msg=msg, info=info)
                return True
        return False

class Sms:
    _last_sms_idx = 0
    msg = None

    def __init__(self, from_msisdn=None, to_msisdn=None):
        Sms._last_sms_idx += 1
        msgs = ['message nr. %d' % Sms._last_sms_idx]
        if from_msisdn or to_msisdn:
            msgs.append(' sent')
        if from_msisdn:
            msgs.append(' from %s' % from_msisdn)
        if to_msisdn:
            msgs.append(' to %s' % to_msisdn)
        self.msg = ''.join(msgs)

    def __str__(self):
        return self.msg

    def __repr__(self):
        return repr(self.msg)

    def __eq__(self, other):
        if isinstance(other, Sms):
            return self.msg == other.msg
        return inself.msg == other

    def matches(self, msg):
        return self.msg == msg

# vim: expandtab tabstop=4 shiftwidth=4
