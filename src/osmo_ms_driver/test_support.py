# osmo_ms_driver: Test helpers and base classes
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

from abc import ABCMeta
from osmo_gsm_tester.core import log

import time

def imsi_ki_gen():
    """
    Generate IMSIs and KIs to be used by test.
    """
    n = 1010000000000
    while True:
        yield ("%.15d" % n, "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00")
        n += 1

class ResultStore(log.Origin):
    """
    The class for results. There should be one result class per test subject.
    Specific tests can use add_result to add their outcome to this object.
    """

    def __init__(self, name):
        super().__init__(log.C_RUN, name)
        self._time_of_registration = None
        self._time_of_launch = None
        self._results = {}

    def set_start_time(self, time):
        assert self._time_of_registration is None
        self._time_of_registration = time

    def set_launch_time(self, time):
        assert self._time_of_launch is None
        self._time_of_launch = time

    def start_time(self):
        return self._time_of_registration or 0

    def launch_time(self):
        return self._time_of_launch or 0

    def set_result(self, key, value):
        """Sets a result with the given key and value."""
        self._results[key] = value

    def get_result(self, key, default=None):
        """Returns the result for the given key or default."""
        return self._results.get(key, default)

    def has_result(self, key):
        """Returns true if there is a value for the key."""
        return self._results.get(key) is not None


class TestBase(log.Origin, metaclass=ABCMeta):
    """Base class for all mass test cases."""

    def __init__(self, name, event_server, results):
        super().__init__(log.C_RUN, name)
        self._event_server = event_server
        self._results = results

    def configure(self, subscribers, mobiles):
        """
        Configures the test given the subscribers.

        The subscriber at index _i_ belongs to the mobile at the
        same index. subscribers[i] == mobiles[i].subscriber().
        """
        pass

    def before_start(self):
        """Prepares the test for starting."""
        pass

    def after_start(self):
        """Finishes the test after starting."""
        pass

    def has_completed(self):
        """Returns true if the test has completed."""
        pass

    def print_stats(self):
        """Prints statistics/results of the test."""
        pass


class TestExecutor(log.Origin):
    """Execute/Wait for a list of tests to complete."""

    def __init__(self):
        super().__init__(log.C_RUN, "executor")
        self._tests = []

    def add_test(self, test):
        self._tests.append(test)

    def configure(self, subscribers, mobiles):
        for test in self._tests:
            test.configure(subscribers, mobiles)

    def before_start(self):
        for test in self._tests:
            test.before_start()

    def after_start(self):
        for test in self._tests:
            test.after_start()

    def print_stats(self):
        """Prints statistics/results of the test."""
        for test in self._tests:
            test.print_stats()

    def all_tests_completed(self):
        """Returns true if all tests completed."""
        for test in self._tests:
            if not test.has_completed():
                return False
        return True

    def wait_for_test(self, loop, deadline):
        """Waits up to the absolute deadline for all tests to complete."""
        while not self.all_tests_completed():
            now_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            sleep_time = deadline - now_time
            if sleep_time < 0:
                break
            loop.schedule_timeout(sleep_time)
            loop.select()
