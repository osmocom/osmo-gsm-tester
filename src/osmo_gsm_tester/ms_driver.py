# ms_driver: Launch OsmocomBB mobile's virtually connected to a BTS
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

from datetime import timedelta
from . import log, util
from osmo_ms_driver.cdf import cdfs
from osmo_ms_driver.event_server import EventServer
from osmo_ms_driver.simple_loop import SimpleLoop
from osmo_ms_driver.location_update_test import MassUpdateLocationTest
from osmo_ms_driver.starter import BinaryOptions

import os.path
import shutil
import tempfile

class Subscriber(log.Origin):
    def __init__(self, imsi, ki):
        super().__init__(log.C_RUN, 'subscriber')
        self._imsi = imsi
        self._ki = ki
        self._auth_algo = "comp128v1"
        self._msisdn = None

    def msisdn(self):
        return self._msisdn

    def set_msisdn(self, msisdn):
        self._msisdn = msisdn

    def imsi(self):
       return self._imsi

    def ki(self):
       return self._ki

    def auth_algo(self):
       return self._auth_algo

class MsDriver(log.Origin):

    def __init__(self, suite_run):
        super().__init__(log.C_RUN, 'ms-driver')
        self._suite_run = suite_run

        # TODO: take config out of the test scenario
        self._num_ms = 10
        self._time_start = timedelta(seconds=60)
        self._time_step = timedelta(milliseconds=100)
        self._test_duration = timedelta(seconds=120)
        self._cdf = cdfs["ease_in_out"](self._time_start, self._time_step)
        self._loop = SimpleLoop()
        self._test_case = None
        self.event_server_sk_tmp_dir = None

        if len(self.event_server_path().encode()) > 107:
            raise log.Error('Path for event_server socket is longer than max allowed len for unix socket path (107):', self.event_server_path())

    def event_server_path(self):
        if self.event_server_sk_tmp_dir is None:
            self.event_server_sk_tmp_dir = tempfile.mkdtemp('', 'ogteventserversk')
        return os.path.join(self.event_server_sk_tmp_dir, 'osmo_ms_driver.unix')

    def configure(self):
        """
        Configures the subscribers, tests and registration server. Needs to be
        called after the complete configuration of this driver.
        """
        event_server_path = self.event_server_path()

        self._ev_server = EventServer("ev_server", event_server_path)
        self._ev_server.listen(self._loop)
        options = BinaryOptions("virtphy", "mobile", None)
        self._test_case = MassUpdateLocationTest("mass", options, self._num_ms, self._cdf,
                                                 self._ev_server,
                                                 util.Dir(self.event_server_sk_tmp_dir),
                                                 suite_run=self._suite_run)

        # TODO: We should pass subscribers down to the test and not get it from
        # there.
        self._subs = [Subscriber(imsi=mob.imsi(), ki=mob.ki()) for mob in self._test_case.mobiles()]


    def ms_subscribers(self):
        """
        Returns a list of 'subscribers' that were configured in the
        current scenario.
        """
        if not hasattr(self, '_subs'):
            self.configure()
        return self._subs

    def run_test(self):
        """
        Runs the configured tests by starting the configured amount of mobile
        devices according to their schedule. Returns once all tests succeeded
        or the configured timeout has passed.
        """
        if not hasattr(self, '_subs'):
            self.configure()
        self._test_case.run_test(self._loop, self._test_duration)

    def print_stats(self):
        """
        Prints statistics about the test run.
        """
        self._test_case.print_stats()

    def cleanup(self):
        """
        Cleans up the driver (e.g. AF_UNIX files).
        """

        # Clean-up the temporary directory.
        if self.event_server_sk_tmp_dir:
            shutil.rmtree(path=self.event_server_sk_tmp_dir)

# vim: expandtab tabstop=4 shiftwidth=4
