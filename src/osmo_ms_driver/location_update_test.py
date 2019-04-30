# osmo_ms_driver: Location Update Test
# Create MS's and wait for the Location Update to succeed.
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

from osmo_gsm_tester import log

from datetime import timedelta

import collections
import json
import time

# Key used for the result dictionary
LU_RESULT_NAME = 'lu_time'

def has_lu_time(result):
    """
    Returns true if a LU occurred.
    """
    return result.has_result(LU_RESULT_NAME)

def lu_time(result):
    """
    Returns the time of the LU occurrence.
    """
    return result.get_result(LU_RESULT_NAME, default=0)

def lu_delay(result):
    """
    Returns the delay from LU success to MS start time.
    """
    return lu_time(result) - result.start_time()

def set_lu_time(result, time):
    """
    Sets/Overrides the time of the LU success for this MS.
    """
    result.set_result(LU_RESULT_NAME, time)


LUStats = collections.namedtuple("LUStats", ["num_attempted", "num_completed",
                                 "min_latency", "max_latency"])

class MassUpdateLocationTest(log.Origin):
    def __init__(self, name, event_server, results):
        super().__init__(log.C_RUN, name)
        self._event_server = event_server
        self._event_server.register(self.handle_msg)
        self._results = results

    def configure(self, num_subscribers):
        self._num_subscribers = num_subscribers
        self._outstanding = num_subscribers

    def handle_msg(self, _data, addr, time):
        data = json.loads(_data.decode())

        if data['type'] == 'event':
            if data['data']['lu_done'] == 1:
                ms = self._results[data['ms']]
                if not has_lu_time(ms):
                    self._outstanding = self._outstanding - 1
                set_lu_time(ms, time)
                self.log("MS performed LU ", ms=ms, at=time, lu_delay=lu_delay(ms))

    def all_completed(self):
        return self._outstanding == 0

    def wait_for_test(self, loop, deadline):
        """Waits up to the absolute deadline for the test to complete."""
        while not self.all_completed():
            now_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            sleep_time = deadline - now_time
            if sleep_time < 0:
                break
            loop.schedule_timeout(sleep_time)
            loop.select()

    def find_min_max(self, results):
        min_value = max_value = None
        for result in results:
            if min_value is None or lu_delay(result) < min_value:
                min_value = lu_delay(result)
            if max_value is None or lu_delay(result) > max_value:
                max_value = lu_delay(result)
        return min_value, max_value

    def get_result_values(self):
        """
        Returns the raw result values of the test run in any order.
        """
        return self._results.values()

    def get_stats(self):
        """
        Returns a statistical summary of the test.
        """
        attempted = self._num_subscribers
        completed = attempted - self._outstanding
        min_latency, max_latency = self.find_min_max(filter(lambda x: has_lu_time(x), self._results.values()))
        return LUStats(attempted, completed, min_latency, max_latency)

    def print_stats(self):
        stats = self.get_stats()
        all_completed = stats.num_attempted == stats.num_completed

        self.log("Tests done", all_completed=all_completed,
                    min=stats.min_latency, max=stats.max_latency)

    def lus_less_than(self, acceptable_delay):
        """
        Returns LUs that completed within the acceptable delay.
        """
        res = []
        for result in self._results.values():
            if not has_lu_time(result):
                continue
            if timedelta(seconds=lu_delay(result)) >= acceptable_delay:
                continue
            res.append(result)
        return res

