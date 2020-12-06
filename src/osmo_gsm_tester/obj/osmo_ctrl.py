
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
    _next_id = 1

    def __init__(self, host, port):
        super().__init__(log.C_BUS, 'Ctrl', host=host, port=port)
        self.host = host
        self.port = port
        self.sck = None

    def next_id(self):
        ret = OsmoCtrl._next_id
        OsmoCtrl._next_id += 1
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

class RateCountersExn(log.Error):
    pass

class RateCounters(dict):
    '''Usage example:
        counter_names = (
                'handover:completed',
                'handover:stopped',
                'handover:no_channel',
                'handover:timeout',
                'handover:failed',
                'handover:error',
                )

        # initialize the listing of CTRL vars of the counters to watch.
        # First on the 'bsc' node:
        #   rate_ctr.abs.bsc.0.handover:completed
        #   rate_ctr.abs.bsc.0.handover:stopped
        #   ...
        counters = RateCounters('bsc', counter_names, from_ctrl=bsc.ctrl)

        # And also add counters for two 'bts' instances:
        #   rate_ctr.abs.bts.0.handover:completed
        #   rate_ctr.abs.bts.0.handover:stopped
        #   ...
        #   rate_ctr.abs.bts.1.handover:completed
        #   ...
        counters.add(RateCounters('bts', counter_names, instances=(0, 1)))

        # read initial counter values, from the bsc_ctrl, as set in
        # counters.from_ctrl in the RateCounters() constructor above.
        counters.read()

        # Do some actions that should increment counters in the SUT
        do_a_handover()

        if approach_without_wait:
            # increment the counters as expected
            counters.inc('bts', 'handover:completed')

            # read counters from CTRL again, and fail if they differ
            counters.verify()

        if approach_with_wait:
            # you can wait for counters to change. counters.changed() does not
            # modify counters' values, just reads values from CTRL and stores
            # the changes in counters.diff.
            wait(counters.changed, timeout=20)

            # log which counters changed by how much, found in counters.diff
            # after each counters.changed() call:
            print(counters.diff.str(skip_zero_vals=True))

            if check_all_vals:
                # Assert all values:
                expected_diff = counters.copy().clear()
                expected_diff.inc('bts', 'handover:completed', instances=(0, 1))
                counters.diff.expect(expected_diff)
            else:
                # Assert only some specific counters:
                expected_diff = RateCounters()
                expected_diff.inc('bts', 'handover:completed', instances=(0, 1))
                counters.diff.expect(expected_diff)

            # update counters to the last read values if desired
            counters.add(counters.diff)
    '''

    def __init__(self, instance_names=(), counter_names=(), instances=0, kinds='abs', init_val=0, from_ctrl=None):
        def init_cb(var):
            self[var] = init_val
        RateCounters.for_each(init_cb, instance_names, counter_names, instances, kinds, results=False)
        self.from_ctrl = from_ctrl
        self.diff = None

    @staticmethod
    def for_each(callback_func, instance_names, counter_names, instances=0, kinds='abs', results=True):
        '''Call callback_func for a set of rate counter var names, mostly
           called by more convenient functions. See inc() for a comprehensive
           explanation.
        '''
        if type(instance_names) is str:
            instance_names = (instance_names, )
        if type(counter_names) is str:
            counter_names = (counter_names, )
        if type(kinds) is str:
            kinds = (kinds, )
        if type(instances) is int:
            instances = (instances, )
        if results is True:
            results = RateCounters()
        elif results is False:
            results = None
        for instance_name in instance_names:
            for instance_nr in instances:
                for counter_name in counter_names:
                    for kind in kinds:
                        var = 'rate_ctr.{kind}.{instance_name}.{instance_nr}.{counter_name}'.format(**locals())
                        result = callback_func(var)
                        if results is not None:
                            results[var] = result
        return results

    def __str__(self):
        return self.str(', ', '')

    def str(self, sep='\n| ', prefix='\n| ', vals=None, skip_zero_vals=False):
        '''The 'vals' arg is useful to print a plain dict() of counter values like a RateCounters class.
           By default print self.'''
        if vals is None:
            vals = self
        return prefix + sep.join('%s = %d' % (var, val) for var, val in sorted(vals.items())
                                 if (not skip_zero_vals) or (val != 0))

    def inc(self, instance_names, counter_names, inc=1, instances=0, kinds='abs'):
        '''Increment a set of counters.
           inc('xyz', 'val')             --> rate_ctr.abs.xyz.0.val += 1

           inc('xyz', ('foo', 'bar'))    --> rate_ctr.abs.xyz.0.foo += 1
                                             rate_ctr.abs.xyz.0.bar += 1

           inc(('xyz', 'pqr'), 'val')    --> rate_ctr.abs.xyz.0.val += 1
                                             rate_ctr.abs.pqr.0.val += 1

           inc('xyz', 'val', instances=range(3))
                                         --> rate_ctr.abs.xyz.0.val += 1
                                             rate_ctr.abs.xyz.1.val += 1
                                             rate_ctr.abs.xyz.2.val += 1
        '''
        def inc_cb(var):
            val = self.get(var, 0)
            val += inc
            self[var] = val
            return val
        RateCounters.for_each(inc_cb, instance_names, counter_names, instances, kinds, results=False)
        return self

    def add(self, rate_counters):
        '''Add the given values up to the values in self.
           rate_counters can be a RateCounters instance or a plain dict of CTRL
           var as key and counter integer as value.
        '''
        for var, add_val in rate_counters.items():
            val = self.get(var, 0)
            val += add_val
            self[var] = val
        return self

    def subtract(self, rate_counters):
        '''Same as add(), but subtract values from self instead.
           Useful to verify counters relative to an arbitrary reference.'''
        for var, subtract_val in rate_counters.items():
            val = self.get(var, 0)
            val -= subtract_val
            self[var] = val
        return self


    def clear(self, val=0):
        '''Set all counts to 0 (or a specific value)'''
        for var in self.keys():
            self[var] = val
        return self

    def copy(self):
        '''Return a copy of all keys and values stored in self.'''
        cpy = RateCounters(from_ctrl = self.from_ctrl)
        cpy.update(self)
        return cpy

    def read(self):
        '''Read all counters from the CTRL connection passed to RateCounters(from_ctrl=x).
           The CTRL must be connected, e.g.
           with bsc.ctrl() as ctrl:
               counters = RateCounters(ctrl)
               counters.read()
        '''
        for var in self.keys():
            self[var] = self.from_ctrl.get_int_var(var)
        self.from_ctrl.dbg('Read counters:', self.str())
        return self

    def verify(self):
        '''Read counters from CTRL and assert that they match the current counts'''
        got_vals = self.copy()
        got_vals.read()
        got_vals.expect(self)

    def changed(self):
        '''Read counters from CTRL, and return True if anyone is different now.
           Store the difference in counts in self.diff (replace self.diff for
           each changed() call). The counts in self are never modified.'''
        self.diff = None
        got_vals = self.copy()
        got_vals.read()
        if self != got_vals:
            self.diff = got_vals
            self.diff.subtract(self)
            self.from_ctrl.dbg('Changed counters:', self.diff.str(skip_zero_vals=True))
            return True
        return False

    def expect(self, expect_vals):
        '''Iterate expect_vals and fail if any counter value differs from self.
           expect_vals can be a RateCounters instance or a plain dict of CTRL
           var as key and counter integer as value.
        '''
        ok = 0
        errs = []
        for var, expect_val in expect_vals.items():
            got_val = self.get(var)
            if got_val is None:
                errs.append('expected {var} == {expect_val}, but no such value found'.format(**locals()))
                continue
            if got_val != expect_val:
                errs.append('expected {var} == {expect_val}, but is {got_val}'.format(**locals()))
                continue
            ok += 1
        if errs:
            self.from_ctrl.dbg('Expected rate counters:', self.str(vals=expect_vals))
            self.from_ctrl.dbg('Got rate counters:', self.str())
            raise RateCountersExn('%d of %d rate counters mismatch:' % (len(errs), len(errs) + ok), '\n| ' + '\n| '.join(errs))
        else:
            self.from_ctrl.log('Verified %d rate counters' % ok)
            self.from_ctrl.dbg('Verified %d rate counters:' % ok, expect_vals)

# vim: expandtab tabstop=4 shiftwidth=4
