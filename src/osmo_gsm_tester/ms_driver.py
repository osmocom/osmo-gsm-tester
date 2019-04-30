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
from osmo_ms_driver.starter import BinaryOptions, MobileTestStarter
from osmo_ms_driver.test_support import TestExecutor

import os.path
import shutil
import tempfile

class MsDriver(log.Origin):

    def __init__(self, suite_run):
        super().__init__(log.C_RUN, 'ms-driver')
        self._suite_run = suite_run

        # TODO: take config out of the test scenario
        self._time_start = timedelta(seconds=60)
        self._time_step = timedelta(milliseconds=100)
        self._test_duration = timedelta(seconds=120)
        self._cdf = cdfs["ease_in_out"](self._time_start, self._time_step)
        self._loop = SimpleLoop()
        self._executor = TestExecutor()
        self.event_server_sk_tmp_dir = None
        self._subscribers = []
        self._configured = False
        self._results = {}

        # Set-up and start the event server
        event_server_path = self.event_server_path()
        if len(event_server_path.encode()) > 107:
            raise log.Error('Path for event_server socket is longer than max allowed len for unix socket path (107):', self.event_server_path())

        self._ev_server = EventServer("ev_server", event_server_path)
        self._ev_server.listen(self._loop)

    def event_server_path(self):
        if self.event_server_sk_tmp_dir is None:
            self.event_server_sk_tmp_dir = tempfile.mkdtemp('', 'ogteventserversk')
        return os.path.join(self.event_server_sk_tmp_dir, 'osmo_ms_driver.unix')

    def build_binary_options(self):
        """Builds an instance of BinaryOptions.

        Populates the BinaryOptions by searching the virtphy and mobile
        application within the trial directory.
        """

        # Get the base directory for the virtphy/mobile application
        inst = util.Dir(os.path.abspath(self._suite_run.trial.get_inst('osmocom-bb')))

        # Assume these are dynamically linked and verify there is a lib dir.
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % inst)
        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        def check_and_return_binary(name):
            """Checks the binary exists and returns the path."""
            binary = inst.child('bin', name)
            if not os.path.isfile(binary):
                raise RuntimeError('Binary missing: %r' % binary)
            return binary

        virtphy = check_and_return_binary('virtphy')
        mobile = check_and_return_binary('mobile')
        return BinaryOptions(virtphy, mobile, env)

    def subscriber_add(self, subscriber):
        """Adds a subscriber to the list of subscribers."""
        self._subscribers.append(subscriber)

    def add_test(self, test_name, **kwargs):
        """
        Instantiates and returns a test for the given name.

        The instance created and added will be returned.
        """
        if test_name == 'update_location':
            test = MassUpdateLocationTest("mass",
                                          self._ev_server, self._results)

        # Verify that a test was instantiated.
        if test_name is None:
            raise Exception("Unknown test_name: " + test_name)

        # Add it to the executor and return it.
        self._executor.add_test(test)
        return test

    def configure(self):
        """
        Configures the subscribers, tests and registration server. Needs to be
        called after the complete configuration of this driver.
        """
        options = self.build_binary_options()
        self._starter = MobileTestStarter("mass", options, self._cdf,
                                          self._ev_server,
                                          util.Dir(self.event_server_sk_tmp_dir),
                                          self._results, suite_run=self._suite_run)

        for sub in self._subscribers:
            self._starter.subscriber_add(sub)

        self._starter.configure_tasks()
        self._executor.configure(self._subscribers, self._starter.mobiles())
        self._configured = True

    def run_test(self):
        """
        Runs the configured tests by starting the configured amount of mobile
        devices according to their schedule. Returns once all tests succeeded
        or the configured timeout has passed.
        """
        if not self._configured:
            self.configure()
        self._executor.before_start()
        deadline = self._starter.start_all(self._loop, self._test_duration)
        self._executor.after_start()
        self._executor.wait_for_test(self._loop, deadline)

    def print_stats(self):
        """
        Prints statistics about the test run.
        """
        self._executor.print_stats()

    def cleanup(self):
        """
        Cleans up the driver (e.g. AF_UNIX files).
        """

        # Clean-up the temporary directory.
        if self.event_server_sk_tmp_dir:
            shutil.rmtree(path=self.event_server_sk_tmp_dir)

# vim: expandtab tabstop=4 shiftwidth=4
