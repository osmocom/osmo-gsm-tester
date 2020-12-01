
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
import re

from ..core import log
from ..core.event_loop import MainLoop

VERB_SET = 'SET'
VERB_GET = 'GET'
VERB_SET_REPLY = 'SET_REPLY'
VERB_GET_REPLY = 'GET_REPLY'
VERB_TRAP = 'TRAP'
VERB_ERROR = 'ERROR'
RECV_VERBS = (VERB_GET_REPLY, VERB_SET_REPLY, VERB_TRAP, VERB_ERROR)
recv_re = re.compile('(%s) ([0-9]+) (.*)' % ('|'.join(RECV_VERBS)),
                     re.MULTILINE + re.DOTALL)

class CtrlInterfaceExn(Exception):
    pass

class OsmoCtrl(log.Origin):

    def __init__(self, host, port):
        super().__init__(log.C_BUS, 'Ctrl', host=host, port=port)
        self.host = host
        self.port = port
        self.sck = None
        self._next_id = 0

    def next_id(self):
        ret = self._next_id
        self._next_id += 1
        return ret

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

    def try_connect(self):
        '''Do a connection attempt, return True when successful, False otherwise.
           Does not raise exceptions, but logs them to the debug log.'''
        assert self.sck is None
        try:
            self.dbg('Connecting')
            sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sck.connect((self.host, self.port))
            except:
                sck.close()
                raise
            # set self.sck only after the connect was successful
            self.sck = sck
            return True
        except:
            self.dbg('Failed to connect', sys.exc_info()[0])
            return False

    def connect(self, timeout=30):
        '''Connect to the CTRL self.host and self.port, retry for 'timeout' seconds.'''
        MainLoop.wait(self.try_connect, timestep=3, timeout=timeout)
        self.sck.setblocking(1)
        self.sck.settimeout(10)

    def disconnect(self):
        if self.sck is None:
            return
        self.dbg('Disconnecting')
        self.sck.close()
        self.sck = None

    def _recv(self, verbs, match_args=None, match_id=None, attempts=10, length=1024):
        '''Receive until a response matching the verbs / args / msg-id is obtained from CTRL.
           The general socket timeout applies for each attempt made, see connect().
           Multiple attempts may be necessary if, for example, intermediate
           messages are received that do not relate to what is expected, like
           TRAPs that are not interesting.

           To receive a GET_REPLY / SET_REPLY:
             verb, rx_id, val = _recv(('GET_REPLY', 'ERROR'), match_id=used_id)
             if verb == 'ERROR':
                 raise CtrlInterfaceExn()
             print(val)

           To receive a TRAP:
             verb, rx_id, val = _recv('TRAP', 'bts_connection_status connected')
             # val == 'bts_connection_status connected'

           If the CTRL is not connected yet, open and close a connection for
           this operation only.
        '''

        # allow calling for both already connected VTY as well as establishing
        # a connection just for this command.
        if self.sck is None:
            with self:
                return self._recv(verbs, match_args=match_args,
                        match_id=match_id, attempts=attempts, length=length)

        if isinstance(verbs, str):
            verbs = (verbs, )

        for i in range(attempts):
            data = self.sck.recv(length)
            self.dbg('Receiving', data=data)
            while len(data) > 0:
                msg, data = self.remove_ipa_ctrl_header(data)
                msg_str = msg.decode('utf-8')

                m = recv_re.fullmatch(msg_str)
                if m is None:
                    raise CtrlInterfaceExn('Received garbage: %r' % data)

                rx_verb, rx_id, rx_args = m.groups()
                rx_id = int(rx_id)

                if match_id is not None and match_id != rx_id:
                    continue

                if verbs and rx_verb not in verbs:
                    continue

                if match_args and not rx_args.startswith(match_args):
                    continue

                return rx_verb, rx_id, rx_args
        raise CtrlInterfaceExn('No answer found: ' + reply_header)

    def _sendrecv(self, verb, send_args, *recv_args, use_id=None, **recv_kwargs):
        '''Send a request and receive a matching response.
           If the CTRL is not connected yet, open and close a connection for
           this operation only.
        '''
        if self.sck is None:
            with self:
                return self._sendrecv(verb, send_args, *recv_args, use_id=use_id, **recv_kwargs)

        if use_id is None:
            use_id = self.next_id()

        # send
        data = '{verb} {use_id} {send_args}'.format(**locals())
        self.dbg('Sending', data=data)
        data = self.prefix_ipa_ctrl_header(data)
        self.sck.send(data)

        # receive reply
        recv_kwargs['match_id'] = use_id
        return self._recv(*recv_args, **recv_kwargs)

    def set_var(self, var, value):
        '''Set the value of a specific variable on a CTRL interface, and return the response, e.g.:
              assert set_var('subscriber-modify-v1', '901701234567,2342') == 'OK'
           If the CTRL is not connected yet, open and close a connection for
           this operation only.
        '''
        verb, rx_id, args = self._sendrecv(VERB_SET, '%s %s' % (var, value), (VERB_SET_REPLY, VERB_ERROR))

        if verb == VERB_ERROR:
            raise CtrlInterfaceExn('SET %s = %s returned %r' % (var, value, ' '.join((verb, str(rx_id), args))))

        var_and_space = var + ' '
        if not args.startswith(var_and_space):
            raise CtrlInterfaceExn('SET %s = %s returned SET_REPLY for different var: %r'
                                   % (var, value, ' '.join((verb, str(rx_id), args))))

        return args[len(var_and_space):]

    def get_var(self, var):
        '''Get the value of a specific variable from a CTRL interface:
              assert get_var('bts.0.oml-connection-state') == 'connected'
           If the CTRL is not connected yet, open and close a connection for
           this operation only.
        '''
        verb, rx_id, args = self._sendrecv(VERB_GET, var, (VERB_GET_REPLY, VERB_ERROR))

        if verb == VERB_ERROR:
            raise CtrlInterfaceExn('GET %s returned %r' % (var, ' '.join((verb, str(rx_id), args))))

        var_and_space = var + ' '
        if not args.startswith(var_and_space):
            raise CtrlInterfaceExn('GET %s returned GET_REPLY for different var: %r'
                                   % (var, value, ' '.join((verb, str(rx_id), args))))

        return args[len(var_and_space):]

    def get_int_var(self, var):
        '''Same as get_var() but return an int'''
        return int(self.get_var(var))

    def get_trap(self, name):
        '''Read from CTRL until a TRAP of this name is received.
           If name is None, any TRAP is returned.
           If the CTRL is not connected yet, open and close a connection for
           this operation only.
        '''
        verb, rx_id, args = self._recv(VERB_TRAP, name)
        name_and_space = var + ' '
        # _recv() should ensure this:
        assert args.startswith(name_and_space)
        return args[len(name_and_space):]

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc_info):
        self.disconnect()

# vim: expandtab tabstop=4 shiftwidth=4
