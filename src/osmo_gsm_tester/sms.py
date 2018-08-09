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

class Sms:
    _last_sms_idx = 0

    def __init__(self, src_msisdn=None, dst_msisdn=None, *tokens):
        Sms._last_sms_idx += 1
        self._src_msisdn = src_msisdn
        self._dst_msisdn = dst_msisdn
        msgs = ['message nr. %d' % Sms._last_sms_idx]
        msgs.extend(tokens)
        if src_msisdn:
            msgs.append('from %s' % src_msisdn)
        if dst_msisdn:
            msgs.append('to %s' % dst_msisdn)
        self.msg = ', '.join(msgs)

    def __str__(self):
        return self.msg

    def __repr__(self):
        return repr(self.msg)

    def __eq__(self, other):
        if isinstance(other, Sms):
            return self.msg == other.msg
        return self.msg == other

    def src_msisdn(self):
        return self._src_msisdn

    def dst_msisdn(self):
        return self._dst_msisdn

    def matches(self, msg):
        return self.msg == msg

# vim: expandtab tabstop=4 shiftwidth=4
