# osmo_gsm_tester: specifics for running an osmo-nitb
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
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

from ..core import log, process

class PcapRecorder(log.Origin):

    def __init__(self, suite_run, run_dir, iface=None, filters='', netns=None):
        self.iface = iface
        if not self.iface:
            self.iface = "any"
        self.filters = filters
        super().__init__(log.C_RUN, 'pcap-recorder_%s' % self.iface, filters=self.filters)
        self.suite_run = suite_run
        self.run_dir = run_dir
        self.netns = netns
        self.start()

    def start(self):
        self.dbg('Recording pcap', self.run_dir, self.filters)
        dumpfile = os.path.join(os.path.abspath(self.run_dir), self.name() + ".pcap")
        popen_args = ('tcpdump', '-n',
                      '-i', self.iface,
                      '-w', dumpfile,
                      self.filters)
        if self.netns:
            self.process = process.NetNSProcess(self.name(), self.run_dir, self.netns, popen_args)
        else:
            self.process = process.Process(self.name(), self.run_dir, popen_args)
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def running(self):
        return not self.process.terminated()

# vim: expandtab tabstop=4 shiftwidth=4
