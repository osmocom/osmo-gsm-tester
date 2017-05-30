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

from . import log, test, util, event_loop

from pydbus import SystemBus, Variant
import time
import pprint

from gi.repository import GLib
glib_main_loop = GLib.MainLoop()
glib_main_ctx = glib_main_loop.get_context()
bus = SystemBus()

I_MODEM = 'org.ofono.Modem'
I_NETREG = 'org.ofono.NetworkRegistration'
I_SMS = 'org.ofono.MessageManager'

class DeferredHandling:
    defer_queue = []

    def __init__(self, dbus_iface, handler):
        self.handler = handler
        self.subscription_id = dbus_iface.connect(self.receive_signal)

    def receive_signal(self, *args, **kwargs):
        DeferredHandling.defer_queue.append((self.handler, args, kwargs))

    @staticmethod
    def handle_queue():
        while DeferredHandling.defer_queue:
            handler, args, kwargs = DeferredHandling.defer_queue.pop(0)
            handler(*args, **kwargs)

def dbus_connect(dbus_iface, handler):
    '''This function shall be used instead of directly connecting DBus signals.
    It ensures that we don't nest a glib main loop within another, and also
    that we receive exceptions raised within the signal handlers. This makes it
    so that a signal handler is invoked only after the DBus polling is through
    by enlisting signals that should be handled in the
    DeferredHandling.defer_queue.'''
    return DeferredHandling(dbus_iface, handler).subscription_id

def poll_glib():
    global glib_main_ctx
    while glib_main_ctx.pending():
        glib_main_ctx.iteration()
    DeferredHandling.handle_queue()

event_loop.register_poll_func(poll_glib)

def systembus_get(path):
    global bus
    return bus.get('org.ofono', path)

def list_modems():
    root = systembus_get('/')
    return sorted(root.GetModems())

class ModemDbusInteraction(log.Origin):
    '''Work around inconveniences specific to pydbus and ofono.
    ofono adds and removes DBus interfaces and notifies about them.
    Upon changes we need a fresh pydbus object to benefit from that.
    Watching the interfaces change is optional; be sure to call
    watch_interfaces() if you'd like to have signals subscribed.
    Related: https://github.com/LEW21/pydbus/issues/56
    '''

    def __init__(self, modem_path):
        self.modem_path = modem_path
        self.set_name(self.modem_path)
        self.set_log_category(log.C_BUS)
        self.watch_props_subscription = None
        self._dbus_obj = None
        self.interfaces = set()

        # A dict listing signal handlers to connect, e.g.
        # { I_SMS: ( ('IncomingMessage', self._on_incoming_message), ), }
        self.required_signals = {}

        # A dict collecting subscription tokens for connected signal handlers.
        # { I_SMS: ( token1, token2, ... ), }
        self.connected_signals = util.listdict()

    def cleanup(self):
        self.unwatch_interfaces()
        for interface_name in list(self.connected_signals.keys()):
            self.remove_signals(interface_name)

    def __del__(self):
        self.cleanup()

    def get_new_dbus_obj(self):
        return systembus_get(self.modem_path)

    def dbus_obj(self):
        if self._dbus_obj is None:
            self._dbus_obj = self.get_new_dbus_obj()
        return self._dbus_obj

    def interface(self, interface_name):
        try:
            return self.dbus_obj()[interface_name]
        except KeyError:
            self.raise_exn('Modem interface is not available:', interface_name)

    def signal(self, interface_name, signal):
        return getattr(self.interface(interface_name), signal)

    def watch_interfaces(self):
        self.unwatch_interfaces()
        # Note: we are watching the properties on a get_new_dbus_obj() that is
        # separate from the one used to interact with interfaces.  We need to
        # refresh the pydbus object to interact with Interfaces that have newly
        # appeared, but exchanging the DBus object to watch Interfaces being
        # enabled and disabled is racy: we may skip some removals and
        # additions. Hence do not exchange this DBus object. We don't even
        # need to store the dbus object used for this, we will not touch it
        # again. We only store the signal subscription.
        self.watch_props_subscription = dbus_connect(self.get_new_dbus_obj().PropertyChanged,
                                                     self.on_property_change)
        self.on_interfaces_change(self.properties().get('Interfaces'))

    def unwatch_interfaces(self):
        if self.watch_props_subscription is None:
            return
        self.watch_props_subscription.disconnect()
        self.watch_props_subscription = None

    def on_property_change(self, name, value):
        if name == 'Interfaces':
            self.on_interfaces_change(value)

    def on_interfaces_change(self, interfaces_now):
        # First some logging.
        now = set(interfaces_now)
        additions = now - self.interfaces
        removals = self.interfaces - now
        self.interfaces = now
        if not (additions or removals):
            # nothing changed.
            return

        if additions:
            self.dbg('interface enabled:', ', '.join(sorted(additions)))

        if removals:
            self.dbg('interface disabled:', ', '.join(sorted(removals)))

        # The dbus object is now stale and needs refreshing before we
        # access the next interface function.
        self._dbus_obj = None

        # If an interface disappeared, disconnect the signal handlers for it.
        # Even though we're going to use a fresh dbus object for new
        # subscriptions, we will still keep active subscriptions alive on the
        # old dbus object which will linger, associated with the respective
        # signal subscription.
        for removed in removals:
            self.remove_signals(removed)

        # Connect signals for added interfaces.
        for interface_name in additions:
            self.connect_signals(interface_name)

    def remove_signals(self, interface_name):
        got = self.connected_signals.pop(interface_name, [])

        if not got:
            return

        self.dbg('Disconnecting', len(got), 'signals for', interface_name)
        for subscription in got:
            subscription.disconnect()

    def connect_signals(self, interface_name):
        # If an interface was added, it must not have existed before. For
        # paranoia, make sure we have no handlers for those.
        self.remove_signals(interface_name)

        want = self.required_signals.get(interface_name, [])
        if not want:
            return

        self.dbg('Connecting', len(want), 'signals for', interface_name)
        for signal, cb in self.required_signals.get(interface_name, []):
            subscription = dbus_connect(self.signal(interface_name, signal), cb)
            self.connected_signals.add(interface_name, subscription)

    def has_interface(self, *interface_names):
        try:
            for interface_name in interface_names:
                self.dbus_obj()[interface_name]
            result = True
        except KeyError:
            result = False
        self.dbg('has_interface(%s) ==' % (', '.join(interface_names)), result)
        return result

    def properties(self, iface=I_MODEM):
        return self.dbus_obj()[iface].GetProperties()

    def property_is(self, name, val, iface=I_MODEM):
        is_val = self.properties(iface).get(name)
        self.dbg(name, '==', is_val)
        return is_val is not None and is_val == val

    def set_bool(self, name, bool_val, iface=I_MODEM):
        # to make sure any pending signals are received before we send out more DBus requests
        event_loop.poll()

        val = bool(bool_val)
        self.log('Setting', name, val)
        self.interface(iface).SetProperty(name, Variant('b', val))

        event_loop.wait(self, self.property_is, name, bool_val)

    def set_powered(self, powered=True):
        self.set_bool('Powered', powered)

    def set_online(self, online=True):
        self.set_bool('Online', online)

    def is_powered(self):
        return self.property_is('Powered', True)

    def is_online(self):
        return self.property_is('Online', True)



class Modem(log.Origin):
    'convenience for ofono Modem interaction'
    msisdn = None
    sms_received_list = None

    def __init__(self, conf):
        self.conf = conf
        self.path = conf.get('path')
        self.set_name(self.path)
        self.set_log_category(log.C_TST)
        self.sms_received_list = []
        self.dbus = ModemDbusInteraction(self.path)
        self.dbus.required_signals = {
                I_SMS: ( ('IncomingMessage', self._on_incoming_message), ),
            }
        self.dbus.watch_interfaces()

    def cleanup(self):
        self.dbus.cleanup()
        self.dbus = None

    def properties(self, *args, **kwargs):
        '''Return a dict of properties on this modem. For the actual arguments,
        see ModemDbusInteraction.properties(), which this function calls.  The
        returned dict is defined by ofono. An example is:
           {'Lockdown': False,
            'Powered': True,
            'Model': 'MC7304',
            'Revision': 'SWI9X15C_05.05.66.00 r29972 CARMD-EV-FRMWR1 2015/10/08 08:36:28',
            'Manufacturer': 'Sierra Wireless, Incorporated',
            'Emergency': False,
            'Interfaces': ['org.ofono.SmartMessaging',
                           'org.ofono.PushNotification',
                           'org.ofono.MessageManager',
                           'org.ofono.NetworkRegistration',
                           'org.ofono.ConnectionManager',
                           'org.ofono.SupplementaryServices',
                           'org.ofono.RadioSettings',
                           'org.ofono.AllowedAccessPoints',
                           'org.ofono.SimManager',
                           'org.ofono.LocationReporting',
                           'org.ofono.VoiceCallManager'],
            'Serial': '356853054230919',
            'Features': ['sms', 'net', 'gprs', 'ussd', 'rat', 'sim', 'gps'],
            'Type': 'hardware',
            'Online': True}
        '''
        return self.dbus.properties(*args, **kwargs)

    def set_powered(self, powered=True):
        return self.dbus.set_powered(powered=powered)

    def set_online(self, online=True):
        return self.dbus.set_online(online=online)

    def is_powered(self):
        return self.dbus.is_powered()

    def is_online(self):
        return self.dbus.is_online()

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

    def connect(self, nitb):
        'set the modem up to connect to MCC+MNC from NITB config'
        self.log('connect to', nitb)
        if self.is_powered():
            self.dbg('is powered')
            self.set_online(False)
            self.set_powered(False)
            event_loop.wait(self, lambda: not self.dbus.has_interface(I_NETREG, I_SMS), timeout=10)
        self.set_powered()
        self.set_online()
        event_loop.wait(self, self.dbus.has_interface, I_NETREG, I_SMS, timeout=10)

    def sms_send(self, to_msisdn_or_modem, *tokens):
        if isinstance(to_msisdn_or_modem, Modem):
            to_msisdn = to_msisdn_or_modem.msisdn
            tokens = list(tokens)
            tokens.append('to ' + to_msisdn_or_modem.name())
        else:
            to_msisdn = str(to_msisdn_or_modem)
        sms = Sms(self.msisdn, to_msisdn, 'from ' + self.name(), *tokens)
        self.log('sending sms to MSISDN', to_msisdn, sms=sms)
        mm = self.dbus.interface(I_SMS)
        mm.SendMessage(to_msisdn, str(sms))
        return sms

    def _on_incoming_message(self, message, info):
        self.log('Incoming SMS:', repr(message))
        self.dbg(info=info)
        self.sms_received_list.append((message, info))

    def sms_was_received(self, sms):
        for msg, info in self.sms_received_list:
            if sms.matches(msg):
                self.log('SMS received as expected:', repr(msg))
                self.dbg(info=info)
                return True
        return False

class Sms:
    _last_sms_idx = 0
    msg = None

    def __init__(self, from_msisdn=None, to_msisdn=None, *tokens):
        Sms._last_sms_idx += 1
        msgs = ['message nr. %d' % Sms._last_sms_idx]
        msgs.extend(tokens)
        if from_msisdn:
            msgs.append('from %s' % from_msisdn)
        if to_msisdn:
            msgs.append('to %s' % to_msisdn)
        self.msg = ', '.join(msgs)

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
