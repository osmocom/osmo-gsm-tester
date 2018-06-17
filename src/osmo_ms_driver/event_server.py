
from osmo_gsm_tester import log
from functools import partial

import time


class EventServer(log.Origin):
    """
    Listen for AF_UNIX/SOCK_DGRAM messages from test apps and
    forward them.
    """
    def __init__(self, name, path):
        super().__init__(log.C_RUN, name)
        self._path = path
        self._handlers = []

    def register(self, cb):
        self._handlers.append(cb)

    def server_path(self):
        return self._path

    def listen(self, loop):
        self._server = loop.create_unix_server(self.read_cb, self._path)

    def read_cb(self, obj, mask):
        # addresss doesn't give us the remote but currently we don't
        # need it.
        data, ancdata, flags, addr = self._server.recvmsg(4096, 4096)
        now = time.clock_gettime(time.CLOCK_MONOTONIC)
        for handler in self._handlers:
            handler(data, addr, now)
