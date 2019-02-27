# osmo_gsm_tester: specifics for running an osmo-sgsn
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
import pprint

from . import log, util, config, template, process, pcap_recorder

class OsmoSgsn(log.Origin):

    def __init__(self, suite_run, hlr, ggsn, ip_address):
        super().__init__(log.C_RUN, 'osmo-sgsn_%s' % ip_address.get('addr'))
        self.run_dir = None
        self.config_file = None
        self.process = None
        self.suite_run = suite_run
        self.hlr = hlr
        self.ggsn = ggsn
        self.ip_address = ip_address

    def start(self):
        self.log('Starting osmo-sgsn')
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-sgsn')))

        binary = inst.child('bin', 'osmo-sgsn')
        if not os.path.isfile(binary):
            raise log.Error('Binary missing:', binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in', inst)

        pcap_recorder.PcapRecorder(self.suite_run, self.run_dir.new_dir('pcap'), None,
                                   'host %s' % self.addr())

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        self.process = process.Process(self.name(), self.run_dir,
                                       (binary,
                                        '-c', os.path.abspath(self.config_file)),
                                       env=env)
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def configure(self):
        self.config_file = self.run_dir.new_file('osmo-sgsn.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(sgsn=config.get_defaults('sgsn'))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, dict(sgsn=dict(ip_address=self.ip_address)))
        config.overlay(values, self.hlr.conf_for_client())
        config.overlay(values, self.ggsn.conf_for_client())

        self.dbg('SGSN CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-sgsn.cfg', values)
            self.dbg(r)
            f.write(r)

    def conf_for_client(self):
        return dict(sgsn=dict(ip_address=self.ip_address))

    def addr(self):
        return self.ip_address.get('addr')

    def running(self):
        return not self.process.terminated()

    def bts_add(self, bts):
        bts.set_sgsn(self)

# vim: expandtab tabstop=4 shiftwidth=4
