# osmo_gsm_tester: DBUS client to talk to ofono
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from . import log, util, sms
from .event_loop import MainLoop

from pydbus import SystemBus, Variant
import time
import pprint
import sys

# Required for Gio.Cancellable.
# See https://lazka.github.io/pgi-docs/Gio-2.0/classes/Cancellable.html#Gio.Cancellable
from gi.module import get_introspection_module
Gio = get_introspection_module('Gio')

from gi.repository import GLib
bus = SystemBus()

I_MODEM = 'org.ofono.Modem'
I_NETREG = 'org.ofono.NetworkRegistration'
I_SMS = 'org.ofono.MessageManager'
I_CONNMGR = 'org.ofono.ConnectionManager'
I_CALLMGR = 'org.ofono.VoiceCallManager'
I_CALL = 'org.ofono.VoiceCall'
I_SS = 'org.ofono.SupplementaryServices'
I_SIMMGR = 'org.ofono.SimManager'

# See https://github.com/intgr/ofono/blob/master/doc/network-api.txt#L78
NETREG_ST_REGISTERED = 'registered'
NETREG_ST_ROAMING = 'roaming'

NETREG_MAX_REGISTER_ATTEMPTS = 3

class DeferredDBus:

    def __init__(self, dbus_iface, handler):
        self.handler = handler
        self.subscription_id = dbus_iface.connect(self.receive_signal)

    def receive_signal(self, *args, **kwargs):
        MainLoop.defer(self.handler, *args, **kwargs)

def dbus_connect(dbus_iface, handler):
    '''This function shall be used instead of directly connecting DBus signals.
    It ensures that we don't nest a glib main loop within another, and also
    that we receive exceptions raised within the signal handlers. This makes it
    so that a signal handler is invoked only after the DBus polling is through
    by enlisting signals that should be handled in the
    DeferredHandling.defer_queue.'''
    return DeferredDBus(dbus_iface, handler).subscription_id

def systembus_get(path):
    global bus
    return bus.get('org.ofono', path)

def list_modems():
    root = systembus_get('/')
    return sorted(root.GetModems())

def get_dbuspath_from_syspath(syspath):
    modems = list_modems()
    for dbuspath, props in modems:
        if props.get('SystemPath', '') == syspath:
            return dbuspath
    raise ValueError('could not find %s in modem list: %s' % (syspath, modems))


def _async_result_handler(obj, result, user_data):
    '''Generic callback dispatcher called from glib loop when an async method
    call has returned. This callback is set up by method dbus_async_call.'''
    (result_callback, error_callback, real_user_data) = user_data
    try:
        ret = obj.call_finish(result)
    except Exception as e:
        if isinstance(e, GLib.Error) and e.code == Gio.IOErrorEnum.CANCELLED:
            log.dbg('DBus method cancelled')
            return

        if error_callback:
            error_callback(obj, e, real_user_data)
        else:
            result_callback(obj, e, real_user_data)
        return

    ret = ret.unpack()
    # to be compatible with standard Python behaviour, unbox
    # single-element tuples and return None for empty result tuples
    if len(ret) == 1:
        ret = ret[0]
    elif len(ret) == 0:
        ret = None
    result_callback(obj, ret, real_user_data)

def dbus_async_call(instance, proxymethod, *proxymethod_args,
                    result_handler=None, error_handler=None,
                    user_data=None, timeout=30, cancellable=None,
                    **proxymethod_kwargs):
    '''pydbus doesn't support asynchronous methods. This method adds support for
    it until pydbus implements it'''

    argdiff = len(proxymethod_args) - len(proxymethod._inargs)
    if argdiff < 0:
        raise TypeError(proxymethod.__qualname__ + " missing {} required positional argument(s)".format(-argdiff))
    elif argdiff > 0:
        raise TypeError(proxymethod.__qualname__ + " takes {} positional argument(s) but {} was/were given".format(len(proxymethod._inargs), len(proxymethod_args)))

    timeout = timeout * 1000
    user_data = (result_handler, error_handler, user_data)

    # See https://lazka.github.io/pgi-docs/Gio-2.0/classes/DBusProxy.html#Gio.DBusProxy.call
    ret = instance._bus.con.call(
        instance._bus_name, instance._path,
        proxymethod._iface_name, proxymethod.__name__,
        GLib.Variant(proxymethod._sinargs, proxymethod_args),
        GLib.VariantType.new(proxymethod._soutargs),
        0, timeout, cancellable,
        _async_result_handler, user_data)

def dbus_call_dismiss_error(log_obj, err_str, method):
    try:
        method()
    except GLib.Error as e:
        if Gio.DBusError.is_remote_error(e) and Gio.DBusError.get_remote_error(e) == err_str:
            log_obj.log('Dismissed Dbus method error: %r' % e)
            return
        raise e

class ModemDbusInteraction(log.Origin):
    '''Work around inconveniences specific to pydbus and ofono.
    ofono adds and removes DBus interfaces and notifies about them.
    Upon changes we need a fresh pydbus object to benefit from that.
    Watching the interfaces change is optional; be sure to call
    watch_interfaces() if you'd like to have signals subscribed.
    Related: https://github.com/LEW21/pydbus/issues/56
    '''

    modem_path = None
    watch_props_subscription = None
    _dbus_obj = None
    interfaces = None

    def __init__(self, modem_path):
        self.modem_path = modem_path
        super().__init__(log.C_BUS, self.modem_path)
        self.interfaces = set()

        # A dict listing signal handlers to connect, e.g.
        # { I_SMS: ( ('IncomingMessage', self._on_incoming_message), ), }
        self.required_signals = {}

        # A dict collecting subscription tokens for connected signal handlers.
        # { I_SMS: ( token1, token2, ... ), }
        self.connected_signals = util.listdict()

    def cleanup(self):
        self.set_powered(False)
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
            raise log.Error('Modem interface is not available:', interface_name)

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
        else:
            self.dbg('%r.PropertyChanged() -> %s=%s' % (I_MODEM, name, value))

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
        MainLoop.poll()

        val = bool(bool_val)
        self.log('Setting', name, val)
        self.interface(iface).SetProperty(name, Variant('b', val))

        MainLoop.wait(self, self.property_is, name, bool_val)

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
    _ki = None
    _imsi = None

    CTX_PROT_IPv4 = 'ip'
    CTX_PROT_IPv6 = 'ipv6'
    CTX_PROT_IPv46 = 'dual'

    def __init__(self, conf):
        self.conf = conf
        self.syspath = conf.get('path')
        self.dbuspath = get_dbuspath_from_syspath(self.syspath)
        super().__init__(log.C_TST, self.dbuspath)
        self.dbg('creating from syspath %s', self.syspath)
        self.sms_received_list = []
        self.dbus = ModemDbusInteraction(self.dbuspath)
        self.register_attempts = 0
        self.call_list = []
        # one Cancellable can handle several concurrent methods.
        self.cancellable = Gio.Cancellable.new()
        self.dbus.required_signals = {
                I_SMS: ( ('IncomingMessage', self._on_incoming_message), ),
                I_NETREG: ( ('PropertyChanged', self._on_netreg_property_changed), ),
                I_CONNMGR: ( ('PropertyChanged', self._on_connmgr_property_changed), ),
                I_CALLMGR: ( ('PropertyChanged', self._on_callmgr_property_changed),
                              ('CallAdded', self._on_callmgr_call_added),
                              ('CallRemoved', self._on_callmgr_call_removed), ),
            }
        self.dbus.watch_interfaces()

    def cleanup(self):
        self.dbg('cleanup')
        if self.cancellable:
            self.cancel_pending_dbus_methods()
            self.cancellable = None
        if self.is_powered():
            self.power_off()
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
        if self._imsi is None:
            if 'sim' in self.features():
                if not self.is_powered():
                        self.set_powered()
                # wait for SimManager iface to appear after we power on
                MainLoop.wait(self, self.dbus.has_interface, I_SIMMGR, timeout=10)
                simmgr = self.dbus.interface(I_SIMMGR)
                # If properties are requested quickly, it may happen that Sim property is still not there.
                MainLoop.wait(self, lambda: simmgr.GetProperties().get('SubscriberIdentity', None) is not None, timeout=10)
                props = simmgr.GetProperties()
                self.dbg('got SIM properties', props)
                self._imsi = props.get('SubscriberIdentity', None)
            else:
                self._imsi = self.conf.get('imsi')
            if self._imsi is None:
                raise log.Error('No IMSI')
        return self._imsi

    def set_ki(self, ki):
        self._ki = ki

    def ki(self):
        if self._ki is not None:
            return self._ki
        return self.conf.get('ki')

    def auth_algo(self):
        return self.conf.get('auth_algo', None)

    def features(self):
        return self.conf.get('features', [])

    def _required_ifaces(self):
        req_ifaces = (I_NETREG,)
        req_ifaces += (I_SMS,) if 'sms' in self.features() else ()
        req_ifaces += (I_SS,) if 'ussd' in self.features() else ()
        req_ifaces += (I_CONNMGR,) if 'gprs' in self.features() else ()
        req_ifaces += (I_SIMMGR,) if 'sim' in self.features() else ()
        return req_ifaces

    def _on_netreg_property_changed(self, name, value):
        self.dbg('%r.PropertyChanged() -> %s=%s' % (I_NETREG, name, value))

    def is_connected(self, mcc_mnc=None):
        netreg = self.dbus.interface(I_NETREG)
        prop = netreg.GetProperties()
        status = prop.get('Status')
        self.dbg('status:', status)
        if not (status == NETREG_ST_REGISTERED or status == NETREG_ST_ROAMING):
            return False
        if mcc_mnc is None: # Any network is fine and we are registered.
            return True
        mcc = prop.get('MobileCountryCode')
        mnc = prop.get('MobileNetworkCode')
        if (mcc, mnc) == mcc_mnc:
            return True
        return False

    def schedule_scan_register(self, mcc_mnc):
        if self.register_attempts > NETREG_MAX_REGISTER_ATTEMPTS:
            raise log.Error('Failed to find Network Operator', mcc_mnc=mcc_mnc, attempts=self.register_attempts)
        self.register_attempts += 1
        netreg = self.dbus.interface(I_NETREG)
        self.dbg('Scanning for operators...')
        # Scan method can take several seconds, and we don't want to block
        # waiting for that. Make it async and try to register when the scan is
        # finished.
        register_func = self.scan_cb_register_automatic if mcc_mnc is None else self.scan_cb_register
        result_handler = lambda obj, result, user_data: MainLoop.defer(register_func, result, user_data)
        error_handler = lambda obj, e, user_data: MainLoop.defer(self.scan_cb_error_handler, e, mcc_mnc)
        dbus_async_call(netreg, netreg.Scan, timeout=30, cancellable=self.cancellable,
                        result_handler=result_handler, error_handler=error_handler,
                        user_data=mcc_mnc)

    def scan_cb_error_handler(self, e, mcc_mnc):
        # It was detected that Scan() method can fail for some modems on some
        # specific circumstances. For instance it fails with org.ofono.Error.Failed
        # if the modem starts to register internally after we started Scan() and
        # the registering succeeds while we are still waiting for Scan() to finsih.
        # So far the easiest seems to check if we are now registered and
        # otherwise schedule a scan again.
        self.err('Scan() failed, retrying if needed:', e)
        if not self.is_connected(mcc_mnc):
            self.schedule_scan_register(mcc_mnc)
        else:
            self.log('Already registered with network', mcc_mnc)

    def scan_cb_register_automatic(self, scanned_operators, mcc_mnc):
        self.dbg('scanned operators: ', scanned_operators);
        for op_path, op_prop in scanned_operators:
            if op_prop.get('Status') == 'current':
                mcc = op_prop.get('MobileCountryCode')
                mnc = op_prop.get('MobileNetworkCode')
                self.log('Already registered with network', (mcc, mnc))
                return
        self.log('Registering with the default network')
        netreg = self.dbus.interface(I_NETREG)
        dbus_call_dismiss_error(self, 'org.ofono.Error.InProgress', netreg.Register)


    def scan_cb_register(self, scanned_operators, mcc_mnc):
        self.dbg('scanned operators: ', scanned_operators);
        matching_op_path = None
        for op_path, op_prop in scanned_operators:
            mcc = op_prop.get('MobileCountryCode')
            mnc = op_prop.get('MobileNetworkCode')
            if (mcc, mnc) == mcc_mnc:
                if op_prop.get('Status') == 'current':
                    self.log('Already registered with network', mcc_mnc)
                    # We discovered the network and we are already registered
                    # with it. Avoid calling op.Register() in this case (it
                    # won't act as a NO-OP, it actually returns an error).
                    return
                matching_op_path = op_path
                break
        if matching_op_path is None:
            self.dbg('Failed to find Network Operator', mcc_mnc=mcc_mnc, attempts=self.register_attempts)
            self.schedule_scan_register(mcc_mnc)
            return
        dbus_op = systembus_get(matching_op_path)
        self.log('Registering with operator', matching_op_path, mcc_mnc)
        try:
            dbus_call_dismiss_error(self, 'org.ofono.Error.InProgress', dbus_op.Register)
        except GLib.Error as e:
            if Gio.DBusError.is_remote_error(e) and Gio.DBusError.get_remote_error(e) == 'org.ofono.Error.NotSupported':
                self.log('modem does not support manual registering, attempting automatic registering')
                self.scan_cb_register_automatic(scanned_operators, mcc_mnc)
                return
            raise e

    def cancel_pending_dbus_methods(self):
        self.cancellable.cancel()
        # Cancel op is applied as a signal coming from glib mainloop, so we
        # need to run it and wait for the callbacks to handle cancellations.
        MainLoop.poll()
        # once it has been triggered, create a new one for next operation:
        self.cancellable = Gio.Cancellable.new()

    def power_off(self):
        if self.dbus.has_interface(I_CONNMGR) and self.is_attached():
            self.detach()
        self.set_online(False)
        self.set_powered(False)
        req_ifaces = self._required_ifaces()
        for iface in req_ifaces:
            MainLoop.wait(self, lambda: not self.dbus.has_interface(iface), timeout=10)

    def power_cycle(self):
        'Power the modem and put it online, power cycle it if it was already on'
        req_ifaces = self._required_ifaces()
        if self.is_powered():
            self.dbg('Power cycling')
            MainLoop.sleep(self, 1.0) # workaround for ofono bug OS#3064
            self.power_off()
        else:
            self.dbg('Powering on')
        self.set_powered()
        self.set_online()
        MainLoop.wait(self, self.dbus.has_interface, *req_ifaces, timeout=10)

    def connect(self, mcc_mnc=None):
        'Connect to MCC+MNC'
        if (mcc_mnc is not None) and (len(mcc_mnc) != 2 or None in mcc_mnc):
            raise log.Error('mcc_mnc value is invalid. It should be None or contain both valid mcc and mnc values:', mcc_mnc=mcc_mnc)
        # if test called connect() before and async scanning has not finished, we need to get rid of it:
        self.cancel_pending_dbus_methods()
        self.power_cycle()
        self.register_attempts = 0
        if self.is_connected(mcc_mnc):
            self.log('Already registered with', mcc_mnc if mcc_mnc else 'default network')
        else:
            self.log('Connect to', mcc_mnc if mcc_mnc else 'default network')
            self.schedule_scan_register(mcc_mnc)

    def is_attached(self):
        connmgr = self.dbus.interface(I_CONNMGR)
        prop = connmgr.GetProperties()
        attached = prop.get('Attached')
        self.dbg('attached:', attached)
        return attached

    def attach(self, allow_roaming=False):
        self.dbg('attach')
        if self.is_attached():
            self.detach()
        connmgr = self.dbus.interface(I_CONNMGR)
        prop = connmgr.SetProperty('RoamingAllowed', Variant('b', allow_roaming))
        prop = connmgr.SetProperty('Powered', Variant('b', True))

    def detach(self):
        self.dbg('detach')
        connmgr = self.dbus.interface(I_CONNMGR)
        prop = connmgr.SetProperty('RoamingAllowed', Variant('b', False))
        prop = connmgr.SetProperty('Powered', Variant('b', False))
        connmgr.DeactivateAll()
        connmgr.ResetContexts() # Requires Powered=false

    def activate_context(self, apn='internet', user='ogt', pwd='', protocol='ip'):
        self.dbg('activate_context', apn=apn, user=user, protocol=protocol)

        connmgr = self.dbus.interface(I_CONNMGR)
        ctx_path = connmgr.AddContext('internet')

        ctx = systembus_get(ctx_path)
        ctx.SetProperty('AccessPointName', Variant('s', apn))
        ctx.SetProperty('Username', Variant('s', user))
        ctx.SetProperty('Password', Variant('s', pwd))
        ctx.SetProperty('Protocol', Variant('s', protocol))

        # Activate can only be called after we are attached
        ctx.SetProperty('Active', Variant('b', True))
        MainLoop.wait(self, lambda: ctx.GetProperties()['Active'] == True)
        self.log('context activated', path=ctx_path, apn=apn, user=user, properties=ctx.GetProperties())
        return ctx_path

    def deactivate_context(self, ctx_id):
        self.dbg('deactivate_context', path=ctx_id)
        ctx = systembus_get(ctx_id)
        ctx.SetProperty('Active', Variant('b', False))
        MainLoop.wait(self, lambda: ctx.GetProperties()['Active'] == False)
        self.dbg('deactivate_context active=false, removing', path=ctx_id)
        connmgr = self.dbus.interface(I_CONNMGR)
        connmgr.RemoveContext(ctx_id)
        self.log('context deactivated', path=ctx_id)

    def sms_send(self, to_msisdn_or_modem, *tokens):
        if isinstance(to_msisdn_or_modem, Modem):
            to_msisdn = to_msisdn_or_modem.msisdn
            tokens = list(tokens)
            tokens.append('to ' + to_msisdn_or_modem.name())
        else:
            to_msisdn = str(to_msisdn_or_modem)
        msg = sms.Sms(self.msisdn, to_msisdn, 'from ' + self.name(), *tokens)
        self.log('sending sms to MSISDN', to_msisdn, sms=msg)
        mm = self.dbus.interface(I_SMS)
        mm.SendMessage(to_msisdn, str(msg))
        return msg

    def _on_incoming_message(self, message, info):
        self.log('Incoming SMS:', repr(message))
        self.dbg(info=info)
        self.sms_received_list.append((message, info))

    def sms_was_received(self, sms_obj):
        for msg, info in self.sms_received_list:
            if sms_obj.matches(msg):
                self.log('SMS received as expected:', repr(msg))
                self.dbg(info=info)
                return True
        return False

    def call_id_list(self):
        self.dbg('call_id_list: %r' % self.call_list)
        return self.call_list

    def call_dial(self, to_msisdn_or_modem):
        if isinstance(to_msisdn_or_modem, Modem):
            to_msisdn = to_msisdn_or_modem.msisdn
        else:
            to_msisdn = str(to_msisdn_or_modem)
        self.dbg('Dialing:', to_msisdn)
        cmgr = self.dbus.interface(I_CALLMGR)
        call_obj_path = cmgr.Dial(to_msisdn, 'default')
        if call_obj_path not in self.call_list:
            self.dbg('Adding %s to call list' % call_obj_path)
            self.call_list.append(call_obj_path)
        else:
            self.dbg('Dial returned already existing call')
        return call_obj_path

    def _find_call_msisdn_state(self, msisdn, state):
        cmgr = self.dbus.interface(I_CALLMGR)
        ret = cmgr.GetCalls()
        for obj_path, props in ret:
            if props['LineIdentification'] == msisdn and props['State'] == state:
                return obj_path
        return None

    def call_wait_incoming(self, caller_msisdn_or_modem, timeout=60):
        if isinstance(caller_msisdn_or_modem, Modem):
            caller_msisdn = caller_msisdn_or_modem.msisdn
        else:
            caller_msisdn = str(caller_msisdn_or_modem)
        self.dbg('Waiting for incoming call from:', caller_msisdn)
        MainLoop.wait(self, lambda: self._find_call_msisdn_state(caller_msisdn, 'incoming') is not None, timeout=timeout)
        return self._find_call_msisdn_state(caller_msisdn, 'incoming')

    def call_answer(self, call_id):
        self.dbg('Answer call %s' % call_id)
        assert self.call_state(call_id) == 'incoming'
        call_dbus_obj = systembus_get(call_id)
        call_dbus_obj.Answer()

    def call_hangup(self, call_id):
        self.dbg('Hang up call %s' % call_id)
        call_dbus_obj = systembus_get(call_id)
        call_dbus_obj.Hangup()

    def call_is_active(self, call_id):
        return self.call_state(call_id) == 'active'

    def call_state(self, call_id):
        call_dbus_obj = systembus_get(call_id)
        props = call_dbus_obj.GetProperties()
        state = props.get('State')
        self.dbg('call state: %s' % state)
        return state

    def _on_callmgr_call_added(self, obj_path, properties):
        self.dbg('%r.CallAdded() -> %s=%r' % (I_CALLMGR, obj_path, repr(properties)))
        if obj_path not in self.call_list:
            self.call_list.append(obj_path)
        else:
            self.dbg('Call already exists %r' % obj_path)

    def _on_callmgr_call_removed(self, obj_path):
        self.dbg('%r.CallRemoved() -> %s' % (I_CALLMGR, obj_path))
        if obj_path in self.call_list:
            self.call_list.remove(obj_path)
        else:
            self.dbg('Trying to remove non-existing call %r' % obj_path)

    def _on_callmgr_property_changed(self, name, value):
        self.dbg('%r.PropertyChanged() -> %s=%s' % (I_CALLMGR, name, value))

    def _on_connmgr_property_changed(self, name, value):
        self.dbg('%r.PropertyChanged() -> %s=%s' % (I_CONNMGR, name, value))

    def info(self, keys=('Manufacturer', 'Model', 'Revision', 'Serial')):
        props = self.properties()
        return ', '.join(['%s: %r'%(k,props.get(k)) for k in keys])

    def log_info(self, *args, **kwargs):
        self.log(self.info(*args, **kwargs))

    def ussd_send(self, command):
        ss = self.dbus.interface(I_SS)
        service_type, response = ss.Initiate(command)
        return response

# vim: expandtab tabstop=4 shiftwidth=4
