# osmo_gsm_tester: VTY connection
#
# Copyright (C) 2020 by sysmocom - s.f.m.c. GmbH
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
import time
import sys

from ..core import log
from ..core.event_loop import MainLoop

class VtyInterfaceExn(Exception):
    pass

class OsmoVty(log.Origin):
    '''Suggested usage:
         with OsmoVty(...) as vty:
             vty.cmds('enable', 'configure network', 'net')
             response = vty.cmd('foo 1 2 3')
             print('\n'.join(response))

       Using 'with' ensures that the connection is closed again.
       There should not be nested 'with' statements on this object.

       Note that test env objects (like tenv.bsc()) may keep a VTY connected until the test exits. A 'with' should not
       be used on those.
    '''

##############
# PROTECTED
##############

    def __init__(self, host, port, prompt=None):
        super().__init__(log.C_BUS, 'Vty', host=host, port=port)
        self.host = host
        self.port = port
        self.sck = None
        self.prompt = prompt
        self.re_prompt = None
        self.this_node = None
        self.this_prompt_char = None
        self.last_node = None
        self.last_prompt_char = None

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

    def _command(self, command_str, timeout=10, strict=True):
        '''Send a command and return the response.'''
        # (copied from https://git.osmocom.org/python/osmo-python-tests/tree/osmopy/osmo_interact/vty.py)
        self.dbg('Sending', command_str=command_str)
        self.sck.send(command_str.encode())

        waited_since = time.time()
        received_lines = []
        last_line = ''

        # (not using MainLoop.wait() to accumulate received responses across
        # iterations)
        while True:
            new_data = self.sck.recv(4096).decode('utf-8')

            last_line = "%s%s" % (last_line, new_data)

            if last_line:
                # Separate the received response into lines.
                # But note: the VTY logging currently separates with '\n\r', not '\r\n',
                # see _vty_output() in libosmocore logging_vty.c.
                # So we need to jump through hoops to not separate 'abc\n\rdef' as
                # [ 'abc', '', 'def' ]; but also not to convert '\r\n\r\n' to '\r\n\n' ('\r{\r\n}\n')
                # Simplest is to just drop all the '\r' and only care about the '\n'.
                last_line = last_line.replace('\r', '')
                lines = last_line.splitlines()
                if last_line.endswith('\n'):
                    received_lines.extend(lines)
                    last_line = ""
                else:
                    # if pkt buffer ends in the middle of a line, we need to keep
                    # last non-finished line:
                    received_lines.extend(lines[:-1])
                    last_line = lines[-1]

            match = self.re_prompt.match(last_line)
            if not match:
                if time.time() - waited_since > timeout:
                    raise IOError("Failed to read data (did the app crash?)")
                MainLoop.sleep(.1)
                continue

            self.last_node = self.this_node
            self.last_prompt_char = self.this_prompt_char
            self.this_node = match.group(1) or None
            self.this_prompt_char = match.group(2)
            break

        # expecting to have received the command we sent as echo, remove it
        clean_command_str = command_str.strip()
        if clean_command_str.endswith('?'):
            clean_command_str = clean_command_str[:-1]
        if received_lines and received_lines[0] == clean_command_str:
            received_lines = received_lines[1:]
        if len(received_lines) > 1:
            self.dbg('Received\n|', '\n| '.join(received_lines), '\n')
        elif len(received_lines) == 1:
            self.dbg('Received', repr(received_lines[0]))

        if received_lines == ['% Unknown command.']:
            errmsg = 'VTY reports unknown command: %r' % command_str
            if strict:
                raise VtyInterfaceExn(errmsg)
            else:
                self.log('ignoring error:', errmsg)

        return received_lines

########################
# PUBLIC - INTERNAL API
########################

    def connect(self, timeout=30):
        '''Connect to the VTY self.host and self.port, retry for 'timeout' seconds.
           connect() and disconnect() are called implicitly when using the 'with' statement.
           See class OsmoVty's doc.
           '''
        MainLoop.wait(self.try_connect, timestep=3, timeout=timeout)
        self.sck.setblocking(1)

        # read first prompt
        # (copied from https://git.osmocom.org/python/osmo-python-tests/tree/osmopy/osmo_interact/vty.py)
        self.this_node = None
        self.this_prompt_char = '>' # slight cheat for initial prompt char
        self.last_node = None
        self.last_prompt_char = None

        data = self.sck.recv(4096)
        if not self.prompt:
            b = data
            b = b[b.rfind(b'\n') + 1:]
            while b and (b[0] < ord('A') or b[0] > ord('z')):
                b = b[1:]
            prompt_str = b.decode('utf-8')
            if '>' in prompt_str:
                self.prompt = prompt_str[:prompt_str.find('>')]
            self.dbg(prompt=self.prompt)
        if not self.prompt:
            raise VtyInterfaceExn('Could not find application name; needed to decode prompts.'
                    ' Initial data was: %r' % data)
        self.re_prompt = re.compile('^%s(?:\(([\w-]*)\))?([#>]) (.*)$' % re.escape(self.prompt))

    def disconnect(self):
        '''Disconnect.
           connect() and disconnect() are called implicitly when using the 'with' statement.
           See class OsmoVty's doc.
           '''
        if self.sck is None:
            return
        self.dbg('Disconnecting')
        self.sck.close()
        self.sck = None

###################
# PUBLIC (test API included)
###################

    def cmd(self, command_str, timeout=10, strict=True):
        '''Send one VTY command and return its response.
           Return a list of strings, one string per line, without line break characters:
             [ 'first line', 'second line', 'third line' ]
           When strict==False, do not raise exceptions on '% Unknown command'.
           If the connection is not yet open, briefly connect for only this command and disconnect again. If it is open,
           use the open connection and leave it open.
        '''
        # allow calling for both already connected VTY as well as establishing
        # a connection just for this command.
        if self.sck is None:
            with self:
                return self.cmd(command_str, timeout, strict)

        # (copied from https://git.osmocom.org/python/osmo-python-tests/tree/osmopy/osmo_interact/vty.py)
        command_str = command_str or '\r'
        if command_str[-1] not in '?\r\t':
            command_str = command_str + '\r'

        received_lines = self._command(command_str, timeout, strict)

        # send escape to cancel the '?' command line
        if command_str[-1] == '?':
            self._command('\x03', timeout)

        return received_lines

    def cmds(self, *cmds, timeout=10, strict=True):
        '''Send a series of commands and return each command's response:
             cmds('foo', 'bar', 'baz') --> [ ['foo line 1','foo line 2'], ['bar line 1'], ['baz line 1']]
           When strict==False, do not raise exceptions on '% Unknown command'.
           If the connection is not yet open, briefly connect for only these commands and disconnect again. If it is
           open, use the open connection and leave it open.
        '''
        # allow calling for both already connected VTY as well as establishing
        # a connection just for this command.
        if self.sck is None:
            with self:
                return self.cmds(*cmds, timeout=timeout, strict=strict)

        responses = []
        for cmd in cmds:
            responses.append(self.cmd(cmd, timeout, strict))
        return responses

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc_info):
        self.disconnect()

# vim: expandtab tabstop=4 shiftwidth=4
