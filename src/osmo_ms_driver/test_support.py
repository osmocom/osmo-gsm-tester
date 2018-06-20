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

from osmo_gsm_tester import log

def imsi_ki_gen():
    """
    Generate IMSIs and KIs to be used by test.
    """
    n = 1010000000000
    while True:
        yield ("%.15d" % n, "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00")
        n += 1

class Results(log.Origin):
    """
    A base class to collect results from tests.
    """

    def __init__(self, name):
        super().__init__(log.C_RUN, name)
        self._time_of_registration = None
        self._time_of_launch = None

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
