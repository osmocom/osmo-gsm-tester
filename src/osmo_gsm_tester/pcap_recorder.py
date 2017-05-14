# osmo_gsm_tester: specifics for running an osmo-nitb
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Pau Espin Pedrol <pespin@sysmocom.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import random
import re
import socket

from . import log, util, config, template, process, osmo_ctrl

class PcapRecorder(log.Origin):

    def __init__(self, suite_run, run_dir, iface=None, addr=None):
        self.suite_run = suite_run
        self.run_dir = run_dir
        self.iface = iface
        if not self.iface:
            self.iface = "any"
        self.addr = addr
        self.set_log_category(log.C_RUN)
        self.set_name('pcap-recorder_%s' % self.iface)
        self.start()

    def start(self):
        self.log('Recording pcap', self.run_dir, self.gen_filter())
        dumpfile = os.path.join(os.path.abspath(self.run_dir), self.name() + ".pcap")
        self.process = process.Process(self.name(), self.run_dir,
                                       ('tcpdump', '-n',
                                       '-i', self.iface,
                                       '-w', dumpfile,
                                       self.gen_filter())
                                       )
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def gen_filter(self):
        filter = ""
        if self.addr:
            filter += 'host ' + self.addr
        return filter

    def running(self):
        return not self.process.terminated()
