# osmo_gsm_tester: specifics for running stress(-ng), a tool to load and stress a computer system
#
# Copyright (C) 2020 by sysmocom - s.f.m.c. GmbH
#
# Author: Pau Espin Pedrol <pespin@sysmocom.de>
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

from ..core import log
from ..core import util
from ..core import process
from ..core import remote

class StressTool(log.Origin):

    STRESS_BIN = 'stress'

##############
# PROTECTED
##############
    def __init__(self, testenv, run_node):
        super().__init__(log.C_RUN, StressTool.STRESS_BIN)
        self.testenv = testenv
        self._run_node = run_node
        self.proc = None
        self.rem_host = None

    def runs_locally(self):
        locally = not self._run_node or self._run_node.is_local()
        return locally

###################
# PUBLIC (test API included)
###################
    def start(self, cpu_workers=0, mem_workers=0, io_workers=0, timeout=0):
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))

        popen_args = (StressTool.STRESS_BIN,)
        if cpu_workers > 0:
            popen_args += ('-c', str(cpu_workers))
        if mem_workers > 0:
            popen_args += ('-m', str(mem_workers))
        if io_workers > 0:
            popen_args += ('-i', str(io_workers))
        if timeout > 0:
            popen_args += ('-t', str(timeout))

        if self.runs_locally():
            self.proc = process.Process(self.name(), self.run_dir, popen_args, env={})
        else:
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            self.proc = self.rem_host.RemoteProcess(self.name(), popen_args, env={})
        # Warning: Be aware that if process ends before test is finished due to
        # "-t timeout" param being set, the test will most probably fail as
        # detected 'early exit' by the testenv.
        self.testenv.remember_to_stop(self.proc)
        self.proc.launch()

    def stop(self):
        self.testenv.stop_process(self.proc)

# vim: expandtab tabstop=4 shiftwidth=4
