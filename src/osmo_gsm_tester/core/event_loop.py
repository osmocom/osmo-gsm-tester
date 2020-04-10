# osmo_gsm_tester: Event loop
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Pau Espin Pedrol <pespin@sysmocom.de>
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

import time
from gi.repository import GLib, GObject

from . import log

class DeferredHandling:

    def __init__(self):
        self.defer_queue = []

    def handle_queue(self):
        while self.defer_queue:
            handler, args, kwargs = self.defer_queue.pop(0)
            handler(*args, **kwargs)

    def defer(self, handler, *args, **kwargs):
        self.defer_queue.append((handler, args, kwargs))

class WaitRequest:

    def __init__(self, condition, condition_args, condition_kwargs, timeout, timestep):
        self.timeout_ack = False
        self.condition_ack = False
        self.timeout_started = time.time()
        self.timeout = timeout
        self.condition = condition
        self.condition_args = condition_args
        self.condition_kwargs = condition_kwargs

    def condition_check(self):
        #print("_wait_condition_check")
        waited = time.time() - self.timeout_started
        if self.condition(*self.condition_args, **self.condition_kwargs):
            self.condition_ack = True
        elif waited > self.timeout:
            self.timeout_ack = True

class EventLoop:

    def __init__(self):
        self.poll_funcs = []
        self.gloop = GLib.MainLoop()
        self.gctx = self.gloop.get_context()
        self.deferred_handling = DeferredHandling()

    def _trigger_cb_func(self, user_data):
            self.defer(user_data)
            return True #to retrigger the timeout

    def defer(self, handler, *args, **kwargs):
        self.deferred_handling.defer(handler, *args, **kwargs)

    def register_poll_func(self, func, timestep=1):
        id = GObject.timeout_add(timestep*1000, self._trigger_cb_func, func) # in 1/1000th of a sec
        self.poll_funcs.append((func, id))

    def unregister_poll_func(self, func):
        for pair in self.poll_funcs:
            f, id = pair
            if f == func:
                GObject.source_remove(id)
                self.poll_funcs.remove(pair)
                return

    def poll(self, may_block=False):
        self.gctx.iteration(may_block)
        self.deferred_handling.handle_queue()

    def wait_no_raise(self, log_obj, condition, condition_args, condition_kwargs, timeout, timestep):
        if not timeout or timeout < 0:
            self = log_obj
            raise log.Error('wait() *must* time out at some point.', timeout=timeout)
        if timestep < 0.1:
            timestep = 0.1

        wait_req = WaitRequest(condition, condition_args, condition_kwargs, timeout, timestep)
        wait_id = GObject.timeout_add(timestep*1000, self._trigger_cb_func, wait_req.condition_check)
        while True:
            try:
                self.poll(may_block=True)
            except Exception: # cleanup of temporary resources in the wait scope
                GObject.source_remove(wait_id)
                raise
            if wait_req.condition_ack or wait_req.timeout_ack:
                GObject.source_remove(wait_id)
                success = wait_req.condition_ack
                return success

    def wait(self, log_obj, condition, *condition_args, timeout=300, timestep=1, **condition_kwargs):
        if not self.wait_no_raise(log_obj, condition, condition_args, condition_kwargs, timeout, timestep):
            log.ctx(log_obj)
            raise log.Error('Wait timeout', condition=condition, timeout=timeout, timestep=timestep)

    def sleep(self, log_obj, seconds):
        assert seconds > 0.
        self.wait_no_raise(log_obj, lambda: False, [], {}, timeout=seconds, timestep=seconds)


MainLoop = EventLoop()


# vim: expandtab tabstop=4 shiftwidth=4
