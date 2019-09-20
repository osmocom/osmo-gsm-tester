# abisipfind: specifics for running abisip-find (osmo-bsc.git)
#
# Copyright (C) 2018-2019 by sysmocom - s.f.m.c. GmbH
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

import os
import re
from . import log, util, process
from .event_loop import MainLoop

class AbisIpFind(log.Origin):
    suite_run = None
    parent_run_dir = None
    run_dir = None
    inst = None
    env = None
    bind_ip = None
    proc = None

    BIN_ABISIP_FIND = 'abisip-find'
    BTS_UNIT_ID_RE = re.compile("Unit_ID='(?P<unit_id>\d+)/\d+/(?P<trx_id>\d+)'")

    def __init__(self, suite_run, parent_run_dir, bind_ip, name_suffix):
        super().__init__(log.C_RUN, AbisIpFind.BIN_ABISIP_FIND + '-' + name_suffix)
        self.suite_run = suite_run
        self.parent_run_dir = parent_run_dir
        self.bind_ip = bind_ip
        self.env = {}

    def start(self):
        self.run_dir = util.Dir(self.parent_run_dir.new_dir(self.name()))
        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-bsc')))

        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in %r' % self.inst)
        ipfind_path = self.inst.child('bin', AbisIpFind.BIN_ABISIP_FIND)
        if not os.path.isfile(ipfind_path):
            raise RuntimeError('Binary missing: %r' % ipfind_path)

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }
        self.proc = process.Process(self.name(), self.run_dir,
                            (ipfind_path, '-i', '1', '-b', self.bind_ip),
                            env=env)
        self.suite_run.remember_to_stop(self.proc)
        self.proc.launch()

    def stop(self):
        self.suite_run.stop_process(self.proc)

    def get_line_by_ip(self, ipaddr):
        """Get latest line (more up to date) from abisip-find based on ip address."""
        token = "IP_Address='%s'" % ipaddr
        myline = None
        for line in (self.proc.get_stdout() or '').splitlines():
            if token in line:
                myline = line
        return myline

    def get_unitid_by_ip(self, ipaddr):
            line = self.get_line_by_ip(ipaddr)
            if line is None:
                return None
            res = AbisIpFind.BTS_UNIT_ID_RE.search(line)
            if res:
                unit_id = int(res.group('unit_id'))
                trx_id = int(res.group('trx_id'))
                return (unit_id, trx_id)
            raise log.Error('abisip-find unit_id field for nanobts %s not found in %s' %(ipaddr, line))

    def bts_ready(self, ipaddr):
        return self.get_line_by_ip(ipaddr) is not None

    def wait_bts_ready(self, ipaddr):
        MainLoop.wait(self, self.bts_ready, ipaddr)
        # There's a period of time after boot in which nanobts answers to
        # abisip-find but tcp RSTs ipacces-config conns. Let's wait in here a
        # bit more time to avoid failing after stating the BTS is ready.
        MainLoop.sleep(self, 2)

# vim: expandtab tabstop=4 shiftwidth=4
