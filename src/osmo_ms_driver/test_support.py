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
from osmo_gsm_tester import log

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

    def configure(self, num_subscribers):
        """Configures the test given the (number) of subscribers."""
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
