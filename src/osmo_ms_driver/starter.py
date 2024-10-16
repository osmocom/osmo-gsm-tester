# osmo_ms_driver: Starter for processes
# Help to start processes over time.
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

from osmo_gsm_tester.core import log, util, process, template

from .test_support import ResultStore

from copy import copy
from datetime import timedelta

import collections
import json
import os
import os.path
import time

BinaryOptions = collections.namedtuple("BinaryOptions", ["virtphy", "mobile", "env"])

class Launcher(log.Origin):
    def __init__(self, binary, env, base_name, name_number, tmp_dir):
        super().__init__(log.C_RUN, "{}/{}".format(base_name, name_number))
        self._binary = binary
        self._env = env
        self._name_number = name_number
        self._tmp_dir = tmp_dir.new_dir(self.name())
        self.run_dir = self._tmp_dir

    def name_number(self):
        return self._name_number

class OsmoVirtPhy(Launcher):
    def __init__(self, binary, env, name_number, tmp_dir):
        super().__init__(binary, env, "osmo-ms-virt-phy", name_number, tmp_dir)
        self._phy_filename = os.path.join(self._tmp_dir, "osmocom_l2_" + self._name_number)
        self._vphy_proc = None

    def phy_filename(self):
        return self._phy_filename

    def start(self, loop, testenv=None):
        if testenv is not None: # overwrite run_dir to store files if run from inside osmo-gsm-tester:
            self.run_dir = util.Dir(testenv.test().get_run_dir().new_dir(self.name()))
        if len(self._phy_filename.encode()) > 107:
            raise log.Error('Path for unix socket is longer than max allowed len for unix socket path (107):', self._phy_filename)

        self.log("Starting virtphy")
        args = [self._binary, "--l1ctl-sock=" + self._phy_filename]
        self._vphy_proc = process.Process(self.name(), self.run_dir,
                                          args, env=self._env)
        if testenv is not None:
            testenv.remember_to_stop(self._vphy_proc)
        self._vphy_proc.launch()

    def verify_ready(self):
        while True:
            print(f"PWD: {os.getcwd()}")
            print(f"Waiting for: {self._phy_filename}")
            if os.path.exists(self._phy_filename):
                return
            time.sleep(5)

    def terminate(self):
        """Clean up things."""
        if self._vphy_proc:
            self._vphy_proc.terminate()

class OsmoMobile(Launcher):
    def __init__(self, binary, env, name_number, tmp_dir, lua_tmpl, cfg_tmpl, subscriber, phy_filename, ev_server_path):
        super().__init__(binary, env, "osmo-ms-mob", name_number, tmp_dir)
        self._lua_template = lua_tmpl
        self._cfg_template = cfg_tmpl
        self._phy_filename = phy_filename
        self._ev_server_path = ev_server_path
        self._imsi = subscriber.imsi()
        self._ki = subscriber.ki()
        self._omob_proc = None

        lua_support = os.path.join(os.path.dirname(__file__), 'lua')
        self._cfg = {
            'test': {
                'event_path': self._ev_server_path,
                'lua_support': lua_support,
            }
        }

    def imsi(self):
        return self._imsi

    def ki(self):
        return self._ki

    def set_cfg_item(self, key, value):
        """
        Sets `key` to `value` inside the test dictionary.

        Used by testcases to pass per MS settings into the lua script
        generator.
        """
        self._cfg['test'][key] = value

    def write_lua_cfg(self):
        lua_cfg_file = self.run_dir.new_file("lua_" + self._name_number + ".lua")
        lua_script = template.render(self._lua_template, self._cfg)
        with open(lua_cfg_file, 'w') as w:
            w.write(lua_script)
        return lua_cfg_file

    def write_mob_cfg(self, lua_filename, phy_filename):
        cfg = {
            'test': {
                'script': lua_filename,
                'virt_phy': phy_filename,
                'imsi': self._imsi,
                'ki_comp128': self._ki,
                'ms_number': self._name_number,
            }
        }
        mob_cfg_file = self.run_dir.new_file("mob_" + self._name_number + ".cfg")
        mob_vty = template.render(self._cfg_template, cfg)
        with open(mob_cfg_file, 'w') as w:
            w.write(mob_vty)
        return mob_cfg_file

    def start(self, loop, testenv=None):
        if testenv is not None: # overwrite run_dir to store files if run from inside osmo-gsm-tester:
            self.run_dir = util.Dir(testenv.test().get_run_dir().new_dir(self.name()))
        lua_filename = self.write_lua_cfg()
        mob_filename = self.write_mob_cfg(lua_filename, self._phy_filename)

        self.log("Starting mobile")
        # Let the kernel pick an unused port for the VTY.
        args = [self._binary, "-c", mob_filename]
        self._omob_proc = process.Process(self.name(), self.run_dir,
                                          args, env=self._env)
        if testenv is not None:
            testenv.remember_to_stop(self._omob_proc)
        self._omob_proc.launch()

    def terminate(self):
        """Clean up things."""
        if self._omob_proc:
            self._omob_proc.terminate()


class MobileTestStarter(log.Origin):
    """
    A test to launch a configurable amount of MS and make them
    execute a Location Updating Procedure.

    Configure the number of MS to be tested and a function that
    decides how quickly to start them and a timeout.
    """

    TEMPLATE_LUA = "osmo-mobile.lua"
    TEMPLATE_CFG = "osmo-mobile.cfg"

    def __init__(self, name, options, cdf_function,
                 event_server, tmp_dir, results, testenv=None):
        super().__init__(log.C_RUN, name)
        self._binary_options = options
        self._cdf = cdf_function
        self._testenv = testenv
        self._tmp_dir = tmp_dir
        self._event_server = event_server
        self._results = results
        self._unstarted = []
        self._mobiles = []
        self._phys = []

        self._started = []
        self._subscribers = []

        self._event_server.register(self.handle_msg)

    def subscriber_add(self, subscriber):
        """
        Adds a subscriber to the list of subscribers.

        Must be called before starting the testcase.
        """
        self._subscribers.append(subscriber)

    def configure_tasks(self):
        """Sets up the test run."""

        self._cdf.set_target(len(self._subscribers))
        self._outstanding = len(self._subscribers)
        for i in range(0, self._outstanding):
            ms_name = "%.5d" % i

            phy = OsmoVirtPhy(self._binary_options.virtphy,
                              self._binary_options.env,
                              ms_name, self._tmp_dir)
            self._phys.append(phy)

            launcher = OsmoMobile(self._binary_options.mobile,
                                self._binary_options.env,
                                ms_name, self._tmp_dir, self.TEMPLATE_LUA,
                                self.TEMPLATE_CFG, self._subscribers[i],
                                phy.phy_filename(),
                                self._event_server.server_path())
            self._results[ms_name] = ResultStore(ms_name)
            self._mobiles.append(launcher)
        self._unstarted = copy(self._mobiles)

    def pre_launch(self, loop):
        """
        We need the virtphy's be ready when the lua script in the
        mobile comes and kicks-off the test. In lua we don't seem to
        be able to just stat/check if a file/socket exists so we need
        to do this from here.
        """
        self.log("Pre-launching all virtphy's")
        for phy in self._phys:
            phy.start(loop, self._testenv)

        self.log("Checking if sockets are in the filesystem:")
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
            ms.start(loop, self._testenv)
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

    def start_all(self, loop, test_duration):
        """
        Starts all processes according to the schedule set by the CDF.
        """
        self.prepare(loop)

        self._to_complete_time = self._start_time + test_duration.total_seconds()
        tick_time = self._start_time

        while len(self._unstarted) > 0:
            tick_time, sleep_time = self.step_once(loop, tick_time)
            now_time = time.clock_gettime(time.CLOCK_MONOTONIC)
            if sleep_time is None:
                sleep_time = self._to_complete_time - now_time
            if sleep_time < 0:
                break
            loop.schedule_timeout(sleep_time)
            loop.select()
        return self._to_complete_time

    def stop_all(self):
        for launcher in self._started:
            launcher.terminate()

    def handle_msg(self, _data, addr, time):
        data = json.loads(_data.decode())

        if data['type'] == 'register':
            ms = self._results[data['ms']]
            ms.set_start_time(time)
            launch_delay = ms.start_time() - ms.launch_time()
            self.log("MS start registered ", ms=ms, at=time, delay=launch_delay)

    def mobiles(self):
        """Returns the list of mobiles configured."""
        return self._mobiles
