# osmo_ms_driver: Locationg Update Test
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
    TEST_TIME = timedelta(seconds=120)

    def __init__(self, name, number_of_ms, cdf_function, event_server, tmp_dir):
        super().__init__(log.C_RUN, name)
        self._number_of_ms = number_of_ms
        self._cdf = cdf_function
        self._cdf.set_target(number_of_ms)
        self._unstarted = []
        self._phys = []
        self._results = {}
        imsi_gen = imsi_ki_gen()

        for i in range(0, number_of_ms):
            ms_name = "%.5d" % i

            phy = OsmoVirtPhy(ms_name, tmp_dir)
            self._phys.append(phy)

            launcher = OsmoMobile(ms_name, tmp_dir, self.TEMPLATE_LUA,
                                self.TEMPLATE_CFG, imsi_gen,
                                phy.phy_filename(),
                                event_server.server_path())
            self._results[ms_name] = LUResult(ms_name)
            self._unstarted.append(launcher)
        self._event_server = event_server
        self._event_server.register(self.handle_msg)

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

    def launch(self, loop):
        self.log("Starting testcase")

        self.pre_launch(loop)

        self._start_time = time.clock_gettime(time.CLOCK_MONOTONIC)
        self._end_time = self._start_time + \
                            self._cdf.duration().total_seconds() + \
                            timedelta(seconds=120).total_seconds()

        current_time = self._start_time
        step_size = self._cdf.step_size().total_seconds()
        self._started = []
        too_slow = 0

        # Start
        self._cdf.step_once()

        while len(self._unstarted) > 0:
            # Check for timeout
            # start pending MS
            while len(self._started) < self._cdf.current_scaled_value() and len(self._unstarted) > 0:
                ms = self._unstarted.pop(0)
                ms.start(loop)
                launch_time = time.clock_gettime(time.CLOCK_MONOTONIC)
                self._results[ms.name_number()].set_launch_time(launch_time)
                self._started.append(ms)

            # Progress and sleep
            self._cdf.step_once()

            now_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            sleep_time = (current_time + step_size) - now_time
            if sleep_time <= 0:
                self.log("Starting too slowly. Moving on",
			target=(current_time + step_size), now=now_time, sleep=sleep_time)
                too_slow += 1
            else:
                loop.schedule_timeout(sleep_time)
                loop.select()
            current_time += step_size

        end_time = time.clock_gettime(time.CLOCK_MONOTONIC)
        self.log("All started...", too_slow=too_slow, duration=end_time - self._start_time)

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
                ms.set_lu_time(time)
                self.log("MS performed LU ", ms=ms, at=time, lu_delay=ms.lu_delay())
        else:
            print(time, data)
            raise Exception("Unknown event type..:" + _data.decode())


    def wait_for_result(self, loop):
        to_complete_time = self._start_time + self.TEST_TIME.total_seconds()

        while True:
            now_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            sleep_time = to_complete_time - now_time
            if sleep_time < 0:
                break
            loop.schedule_timeout(sleep_time)
            loop.select()

    def print_stats(self):
        from functools import reduce
        all_completed = reduce(lambda b, ms: b and ms.lu_time() is not None, self._results.values(), True)
        min_value = min(self._results.values(), key=lambda x: x.lu_delay())
        max_value = max(self._results.values(), key=lambda x: x.lu_delay())

        self.log("Tests done", all_completed=all_completed,
                    min=min_value.lu_delay(), max=max_value.lu_delay())
