# osmo_gsm_tester: specifics for running an iperf3 client and server
#
# Copyright (C) 2018 by sysmocom - s.f.m.c. GmbH
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
import json

from . import log, util, process, pcap_recorder

DEFAULT_SRV_PORT = 5003

class IPerf3Server(log.Origin):

    def __init__(self, suite_run, ip_address):
        super().__init__(log.C_RUN, 'iperf3-srv_%s' % ip_address.get('addr'))
        self.run_dir = None
        self.config_file = None
        self.process = None
        self.suite_run = suite_run
        self.ip_address = ip_address
        self._port = DEFAULT_SRV_PORT

    def start(self):
        self.log('Starting iperf3-srv')
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))

        pcap_recorder.PcapRecorder(self.suite_run, self.run_dir.new_dir('pcap'), None,
                                   'host %s and port not 22' % self.addr())

        self.log_file = self.run_dir.new_file('iperf3_srv.json')
        self.process = process.Process(self.name(), self.run_dir,
                                       ('iperf3', '-s', '-B', self.addr(),
                                        '-p', str(self._port), '-J',
                                        '--logfile', os.path.abspath(self.log_file)),
                                       env={})
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def stop(self):
        self.suite_run.stop_process(self.process)

    def get_results(self):
        with open(self.log_file) as f:
                data = json.load(f)
        return data

    def addr(self):
        return self.ip_address.get('addr')

    def port(self):
        return self._port

    def running(self):
        return not self.process.terminated()

    def create_client(self):
        return IPerf3Client(self.suite_run, self)

class IPerf3Client(log.Origin):

    def __init__(self, suite_run, iperf3srv):
        super().__init__(log.C_RUN, 'iperf3-cli_%s' % iperf3srv.addr())
        self.run_dir = None
        self.config_file = None
        self.process = None
        self.server = iperf3srv
        self.suite_run = suite_run

    def run_test(self, netns=None):
        self.log('Starting iperf3-client connecting to %s:%d' % (self.server.addr(), self.server.port()))
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))

        pcap_recorder.PcapRecorder(self.suite_run, self.run_dir.new_dir('pcap'), None,
                                   'host %s and port not 22' % self.server.addr(), netns)

        self.log_file = self.run_dir.new_file('iperf3_cli.json')
        popen_args = ('iperf3', '-c',  self.server.addr(),
                      '-p', str(self.server.port()), '-J',
                      '--logfile', os.path.abspath(self.log_file))
        if netns:
            self.process = process.NetNSProcess(self.name(), self.run_dir, netns, popen_args, env={})
        else:
            self.process = process.Process(self.name(), self.run_dir, popen_args, env={})
        process.run_proc_sync(self.process)
        return self.get_results()

    def get_results(self):
        with open(self.log_file) as f:
                data = json.load(f)
        return data

# vim: expandtab tabstop=4 shiftwidth=4
