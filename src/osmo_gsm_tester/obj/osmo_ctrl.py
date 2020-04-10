
# osmo_gsm_tester: specifics for running a sysmoBTS
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

import socket
import struct

from ..core import log

class CtrlInterfaceExn(Exception):
    pass

class OsmoCtrl(log.Origin):

    def __init__(self, host, port):
        super().__init__(log.C_BUS, 'Ctrl', host=host, port=port)
        self.host = host
        self.port = port
        self.sck = None

    def prefix_ipa_ctrl_header(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        s = struct.pack(">HBB", len(data)+1, 0xee, 0)
        return s + data

    def remove_ipa_ctrl_header(self, data):
        if (len(data) < 4):
            raise CtrlInterfaceExn("Answer too short!")
        (plen, ipa_proto, osmo_proto) = struct.unpack(">HBB", data[:4])
        if (plen + 3 > len(data)):
            self.err('Warning: Wrong payload length', expected=plen, got=len(data)-3)
        if (ipa_proto != 0xee or osmo_proto != 0):
            raise CtrlInterfaceExn("Wrong protocol in answer!")
        return data[4:plen+3], data[plen+3:]

    def connect(self):
        self.dbg('Connecting')
        self.sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sck.connect((self.host, self.port))
        self.sck.setblocking(1)

    def disconnect(self):
        self.dbg('Disconnecting')
        if self.sck is not None:
            self.sck.close()

    def _send(self, data):
        self.dbg('Sending', data=data)
        data = self.prefix_ipa_ctrl_header(data)
        self.sck.send(data)

    def receive(self, length = 1024):
        data = self.sck.recv(length)
        self.dbg('Receiving', data=data)
        return data

    def do_set(self, var, value, id=0):
        setmsg = "SET %s %s %s" %(id, var, value)
        self._send(setmsg)

    def do_get(self, var, id=0):
        getmsg = "GET %s %s" %(id, var)
        self._send(getmsg)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc_info):
        self.disconnect()

# vim: expandtab tabstop=4 shiftwidth=4
