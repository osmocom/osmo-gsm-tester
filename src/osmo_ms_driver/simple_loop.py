# osmo_ms_driver: Event loop because asyncio is not up to the job
#
# Copyright (C) 2018 by Holger Hans Peter Freyther
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

from osmo_gsm_tester.core import log

import os
import selectors
import socket


class SimpleLoop(log.Origin):
    def __init__(self):
        super().__init__(log.C_RUN, "SimpleLoop")
        self._loop = selectors.DefaultSelector()
        self._timeout = None

    def register_fd(self, fd, event, callback):
        self._loop.register(fd, event, callback)

    def schedule_timeout(self, timeout):
        assert self._timeout == None
        self._timeout = timeout

    def create_unix_server(self, cb, path):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

        if len(path.encode()) > 107:
            raise log.Error('Path for unix socket is longer than max allowed len for unix socket path (107):', path)

        # If not a special Linux namespace...
        if path[0] != '\0':
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass

        # Now bind+listen+NONBLOCK
        sock.bind(path)
        sock.setblocking(False)

        self.register_fd(sock.fileno(), selectors.EVENT_READ, cb)
        return sock

    def select(self):
        events = self._loop.select(timeout=self._timeout)
        self._timeout = None
        for key, mask in events:
            key.data(key.fileobj, mask)
