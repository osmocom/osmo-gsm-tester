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
        return self.msg == other

    def matches(self, msg):
        return self.msg == msg

# vim: expandtab tabstop=4 shiftwidth=4
