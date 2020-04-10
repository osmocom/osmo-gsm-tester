# osmo_gsm_tester: SMPP ESME to talk to SMSC
#
# Copyright (C) 2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Pau Espin Pedrol <pespin@sysmocom.de>
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

import smpplib.gsm
import smpplib.client
import smpplib.command
import smpplib.consts
import smpplib.exceptions

from .core import log
from .core.event_loop import MainLoop

# if you want to know what's happening inside python-smpplib
#import logging
#logging.basicConfig(level='DEBUG')

MAX_SYS_ID_LEN = 16
MAX_PASSWD_LEN = 16

class Esme(log.Origin):

    MSGMODE_TRANSACTION = smpplib.consts.SMPP_MSGMODE_FORWARD
    MSGMODE_STOREFORWARD = smpplib.consts.SMPP_MSGMODE_STOREFORWARD

    def __init__(self, msisdn):
        self.msisdn = msisdn
        # Get last characters of msisdn to stay inside MAX_SYS_ID_LEN. Similar to modulus operator.
        self.set_system_id('esme-' + self.msisdn[-11:])
        super().__init__(log.C_TST, self.system_id)
        self.client = None
        self.smsc = None
        self.set_password('esme-pwd')
        self.connected = False
        self.bound = False
        self.listening = False
        self.references_pending_receipt = []
        self.next_user_message_reference = 1

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        try:
            self.disconnect()
        except smpplib.exceptions.ConnectionError:
            pass

    def set_smsc(self, smsc):
        self.smsc = smsc

    def set_system_id(self, name):
        if len(name) > MAX_SYS_ID_LEN:
            raise log.Error('Esme system_id too long! %d vs %d', len(name), MAX_SYS_ID_LEN)
        self.system_id = name

    def set_password(self, password):
        if len(password) > MAX_PASSWD_LEN:
            raise log.Error('Esme password too long! %d vs %d', len(password), MAX_PASSWD_LEN)
        self.password = password

    def conf_for_smsc(self):
        config = { 'system_id': self.system_id, 'password': self.password }
        return config

    def poll(self):
        self.client.poll()

    def start_listening(self):
        self.listening = True
        MainLoop.register_poll_func(self.poll)

    def stop_listening(self):
        if not self.listening:
            return
        self.listening = False
        # Empty the queue before processing the unbind + disconnect PDUs
        MainLoop.unregister_poll_func(self.poll)
        self.poll()

    def connect(self):
        host, port = self.smsc.addr_port
        if self.client:
            self.disconnect()
        self.client = smpplib.client.Client(host, port, timeout=None)
        self.client.set_message_sent_handler(
            lambda pdu: self.dbg('Unhandled submit_sm_resp message:', pdu.sequence) )
        self.client.set_message_received_handler(self._message_received_handler)
        self.client.connect()
        self.connected = True
        self.client.bind_transceiver(system_id=self.system_id, password=self.password)
        self.bound = True
        self.log('Connected and bound successfully to %s (%s:%d). Starting to listen.' % (self.system_id, host, port))
        self.start_listening()

    def disconnect(self):
        self.stop_listening()
        if self.bound:
            self.client.unbind()
            self.bound = False
        if self.connected:
            self.client.disconnect()
            self.connected = False

    def _message_received_handler(self, pdu, *args):
        self.dbg('message received:', seq=pdu.sequence)
        if isinstance(pdu, smpplib.command.AlertNotification):
            self.dbg('message received:  AlertNotification:', ms_availability_status=pdu.ms_availability_status)
        elif isinstance(pdu, smpplib.command.DeliverSM):
            umref = int(pdu.user_message_reference)
            self.dbg('message received: DeliverSM', references_pending_receipt=self.references_pending_receipt, user_message_reference=umref)
            self.references_pending_receipt.remove(umref)

    def receipt_was_received(self, umref):
        return umref not in self.references_pending_receipt

    def run_method_expect_failure(self, errcode, method, *args):
        try:
            method(*args)
            #it should not succeed, raise an exception:
            raise log.Error('SMPP Failure: %s should have failed with SMPP error %d (%s) but succeeded.' % (method, errcode, smpplib.consts.DESCRIPTIONS[errcode]))
        except smpplib.exceptions.PDUError as e:
            if e.args[1] != errcode:
                raise e
            self.dbg('Expected failure triggered: %d' % errcode)

    def sms_send(self, sms_obj, mode, receipt=False):
        parts, encoding_flag, msg_type_flag = smpplib.gsm.make_parts(str(sms_obj))
        seqs = []
        self.log('Sending SMS "%s" to %s' % (str(sms_obj), sms_obj.dst_msisdn()))
        umref = self.next_user_message_reference
        self.next_user_message_reference = (self.next_user_message_reference + 1) % (1 << 8)
        for part in parts:
            pdu = self.client.send_message(
                source_addr_ton=smpplib.consts.SMPP_TON_INTL,
                source_addr_npi=smpplib.consts.SMPP_NPI_ISDN,
                source_addr=sms_obj.src_msisdn(),
                dest_addr_ton=smpplib.consts.SMPP_TON_INTL,
                dest_addr_npi=smpplib.consts.SMPP_NPI_ISDN,
                destination_addr=sms_obj.dst_msisdn(),
                short_message=part,
                data_coding=encoding_flag,
                esm_class=mode,
                registered_delivery=receipt,
                user_message_reference=umref,
                )

            self.dbg('sent part with seq', pdu.sequence)
            seqs.append(pdu.sequence)
        if receipt:
            self.references_pending_receipt.append(umref)
        return umref, seqs

    def _process_pdus_pending(self, pdu, **kwargs):
        self.dbg('message sent resp with seq', pdu.sequence, ', pdus_pending:', self.pdus_pending)
        if pdu.sequence in self.pdus_pending:
            self.pdus_pending.remove(pdu.sequence)

    def sms_send_wait_resp(self, sms_obj, mode, receipt=False):
        old_func = self.client.message_sent_handler
        try:
            umref, self.pdus_pending = self.sms_send(sms_obj, mode, receipt)
            self.dbg('pdus_pending:', self.pdus_pending)
            self.client.set_message_sent_handler(self._process_pdus_pending)
            MainLoop.wait(self, lambda: len(self.pdus_pending) == 0, timeout=10)
            return umref
        finally:
            self.client.set_message_sent_handler(old_func)

# vim: expandtab tabstop=4 shiftwidth=4
