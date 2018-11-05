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

from osmo_gsm_tester import log, process, template

import collections
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

    def name_number(self):
        return self._name_number

class OsmoVirtPhy(Launcher):
    def __init__(self, binary, env, name_number, tmp_dir):
        super().__init__(binary, env, "osmo-ms-virt-phy", name_number, tmp_dir)
        self._phy_filename = os.path.join(self._tmp_dir, "osmocom_l2_" + self._name_number)
        self._vphy_proc = None

    def phy_filename(self):
        return self._phy_filename

    def start(self, loop, suite_run=None):
        if len(self._phy_filename.encode()) > 107:
            raise log.Error('Path for unix socket is longer than max allowed len for unix socket path (107):', self._phy_filename)

        self.log("Starting virtphy")
        args = [self._binary, "--l1ctl-sock=" + self._phy_filename]
        self._vphy_proc = process.Process(self.name(), self._tmp_dir,
                                          args, env=self._env)
        if suite_run:
            suite_run.remember_to_stop(self._vphy_proc)
        self._vphy_proc.launch()

    def verify_ready(self):
        while True:
            if os.path.exists(self._phy_filename):
                return
            time.sleep(0.2)

    def terminate(self):
        """Clean up things."""
        if self._vphy_proc:
            self._vphy_proc.terminate()

class OsmoMobile(Launcher):
    def __init__(self, binary, env, name_number, tmp_dir, lua_tmpl, cfg_tmpl, imsi_ki_generator, phy_filename, ev_server_path):
        super().__init__(binary, env, "osmo-ms-mob", name_number, tmp_dir)
        self._lua_template = lua_tmpl
        self._cfg_template = cfg_tmpl
        self._imsi_ki_generator = imsi_ki_generator
        self._phy_filename = phy_filename
        self._ev_server_path = ev_server_path
        self._imsi, self._ki = next(self._imsi_ki_generator)
        self._omob_proc = None

    def imsi(self):
        return self._imsi

    def ki(self):
        return self._ki

    def write_lua_cfg(self):
        lua_support = os.path.join(os.path.dirname(__file__), 'lua')
        cfg = {
            'test': {
                'event_path': self._ev_server_path,
                'lua_support': lua_support,
            }
        }
        lua_cfg_file = os.path.join(self._tmp_dir, "lua_" + self._name_number + ".lua")
        lua_script = template.render(self._lua_template, cfg)
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
        mob_cfg_file = os.path.join(self._tmp_dir, "mob_" + self._name_number + ".cfg")
        mob_vty = template.render(self._cfg_template, cfg)
        with open(mob_cfg_file, 'w') as w:
            w.write(mob_vty)
        return mob_cfg_file

    def start(self, loop, suite_run=None):
        lua_filename = self.write_lua_cfg()
        mob_filename = self.write_mob_cfg(lua_filename, self._phy_filename)

        self.log("Starting mobile")
        # Let the kernel pick an unused port for the VTY.
        args = [self._binary, "-c", mob_filename, "--vty-port=0"]
        self._omob_proc = process.Process(self.name(), self._tmp_dir,
                                          args, env=self._env)
        if suite_run:
            suite_run.remember_to_stop(self._omob_proc)
        self._omob_proc.launch()

    def terminate(self):
        """Clean up things."""
        if self._omob_proc:
            self._omob_proc.terminate()
