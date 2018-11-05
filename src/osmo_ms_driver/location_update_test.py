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

from copy import copy
from osmo_gsm_tester import log
from .starter import OsmoVirtPhy, OsmoMobile
from .test_support import imsi_ki_gen, Results

from datetime import timedelta

import time

class LUResult(Results):

    def __init__(self, name):
        super().__init__(name)
        self._time_of_lu = None

    def set_lu_time(self, time):
        assert self._time_of_lu is None
        self._time_of_lu = time

    def has_lu_time(self):
        return self._time_of_lu is not None

    def lu_time(self):
        return self._time_of_lu or 0

    def lu_delay(self):
        return self.lu_time() - self.start_time()

class MassUpdateLocationTest(log.Origin):
    """
    A test to launch a configurable amount of MS and make them
    execute a Location Updating Procedure.

    Configure the number of MS to be tested and a function that
    decides how quickly to start them and a timeout.
    """

    TEMPLATE_LUA = "osmo-mobile-lu.lua"
    TEMPLATE_CFG = "osmo-mobile.cfg"

    def __init__(self, name, options, number_of_ms, cdf_function, event_server, tmp_dir):
        super().__init__(log.C_RUN, name)
        self._binary_options = options
        self._number_of_ms = number_of_ms
        self._cdf = cdf_function
        self._cdf.set_target(number_of_ms)
        self._unstarted = []
        self._mobiles = []
        self._phys = []
        self._results = {}
        imsi_gen = imsi_ki_gen()

        self._outstanding = number_of_ms
        for i in range(0, number_of_ms):
            ms_name = "%.5d" % i

            phy = OsmoVirtPhy(options.virtphy, options.env,
                              ms_name, tmp_dir)
            self._phys.append(phy)

            launcher = OsmoMobile(options.mobile, options.env,
                                ms_name, tmp_dir, self.TEMPLATE_LUA,
                                self.TEMPLATE_CFG, imsi_gen,
                                phy.phy_filename(),
                                event_server.server_path())
            self._results[ms_name] = LUResult(ms_name)
            self._mobiles.append(launcher)
        self._event_server = event_server
        self._event_server.register(self.handle_msg)
        self._unstarted = copy(self._mobiles)
        self._started = []

    def mobiles(self):
        return self._mobiles

    def pre_launch(self, loop):
        """
        We need the virtphy's be ready when the lua script in the
        mobile comes and kicks-off the test. In lua we don't seem to
        be able to just stat/check if a file/socket exists so we need
        to do this from here.
        """
        self.log("Pre-launching all virtphy's")
        for phy in self._phys:
            phy.start(loop)

        self.log("Checking if sockets are in the filesystem")
        for phy in self._phys:
            phy.verify_ready()

    def prepare(self, loop):
        self.log("Starting testcase")

        self.pre_launch(loop)

        self._start_time = time.clock_gettime(time.CLOCK_MONOTONIC)
        self._end_time = self._start_time + \
                            self._cdf.duration().total_seconds() + \
                            timedelta(seconds=120).total_seconds()

        self._started = []
        self._too_slow = 0

    def step_once(self, loop, current_time):
        if len(self._unstarted) <= 0:
            return current_time, None

        step_size = self._cdf.step_size().total_seconds()

        # Start
        self._cdf.step_once()

        # Check for timeout
        # start pending MS
        while len(self._started) < self._cdf.current_scaled_value() and len(self._unstarted) > 0:
            ms = self._unstarted.pop(0)
            ms.start(loop)
            launch_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            self._results[ms.name_number()].set_launch_time(launch_time)
            self._started.append(ms)

        now_time = time.clock_gettime(time.CLOCK_MONOTONIC)
        sleep_time = (current_time + step_size) - now_time
        if sleep_time <= 0:
            self.log("Starting too slowly. Moving on",
		    target=(current_time + step_size), now=now_time, sleep=sleep_time)
            self._too_slow += 1
            sleep_time = 0

        if len(self._unstarted) == 0:
            end_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            self.log("All started...", too_slow=self._too_slow, duration=end_time - self._start_time)
            return current_time, None

        return current_time + step_size, sleep_time

    def run_test(self, loop, test_duration):
        self.prepare(loop)

        to_complete_time = self._start_time + test_duration.total_seconds()
        tick_time = self._start_time

        while not self.all_completed():
            tick_time, sleep_time = self.step_once(loop, tick_time)
            now_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            if sleep_time is None:
                sleep_time = to_complete_time - now_time
            if sleep_time < 0:
                break
            loop.schedule_timeout(sleep_time)
            loop.select()

    def stop_all(self):
        for launcher in self._started:
            launcher.kill()

    def handle_msg(self, _data, addr, time):
        import json
        data = json.loads(_data.decode())

        if data['type'] == 'register':
            ms = self._results[data['ms']]
            ms.set_start_time(time)
            launch_delay = ms.start_time() - ms.launch_time()
            self.log("MS start registered ", ms=ms, at=time, delay=launch_delay)
        elif data['type'] == 'event':
            if data['data']['lu_done'] == 1:
                ms = self._results[data['ms']]
                if not ms.has_lu_time():
                    self._outstanding = self._outstanding - 1
                ms.set_lu_time(time)
                self.log("MS performed LU ", ms=ms, at=time, lu_delay=ms.lu_delay())
        else:
            print(time, data)
            raise Exception("Unknown event type..:" + _data.decode())


    def all_completed(self):
        return self._outstanding == 0

    def results_min_max(self, results):
        min_value = max_value = None
        for result in results:
            if min_value is None or result.lu_delay() < min_value:
                min_value = result.lu_delay()
            if max_value is None or result.lu_delay() > max_value:
                max_value = result.lu_delay()
        return min_value, max_value

    def print_stats(self):
        all_completed = self.all_completed()
        min_value, max_value = self.results_min_max(filter(lambda x: x.has_lu_time(), self._results.values()))

        self.log("Tests done", all_completed=all_completed,
                    min=min_value, max=max_value)
