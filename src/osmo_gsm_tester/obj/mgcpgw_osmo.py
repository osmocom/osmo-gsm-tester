# osmo_gsm_tester: specifics for running an osmo-mgcp-gw (osmo-bsc_mgcp)
#
# Copyright (C) 2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
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

from ..core import log, util, config, template, process
from . import pcap_recorder

class OsmoMgcpgw(log.Origin):

    def __init__(self, testenv, ip_address, bts_ip):
        super().__init__(log.C_RUN, 'osmo-mgcpgw_%s' % ip_address.get('addr'))
        self.run_dir = None
        self.config_file = None
        self.process = None
        self.testenv = testenv
        self.ip_address = ip_address
        # hack: so far mgcpgw needs one specific BTS IP.
        self.bts_ip = bts_ip

    def start(self):
        self.log('Starting osmo-mgcpgw')
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()
        inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('osmo-nitb')))
        binary = inst.child('bin', 'osmo-bsc_mgcp')
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % inst)

        pcap_recorder.PcapRecorder(self.testenv, self.run_dir.new_dir('pcap'), None,
                                   'host %s and port not 22' % self.addr())

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        self.process = process.Process(self.name(), self.run_dir,
                                       (binary, '-c',
                                        os.path.abspath(self.config_file)),
                                       env=env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def configure(self):
        self.config_file = self.run_dir.new_file('osmo-mgcpgw.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(mgcpgw=config.get_defaults('mgcpgw'))
        config.overlay(values, self.testenv.suite().config())
        config.overlay(values, dict(mgcpgw=dict(ip_address=self.ip_address, bts_ip=self.bts_ip)))

        self.dbg('MGCPGW CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-mgcpgw.cfg', values)
            self.dbg(r)
            f.write(r)

    def addr(self):
        return self.ip_address.get('addr')

    def conf_for_msc(self):
        return dict(mgw=dict(ip_address=self.ip_address))

    def running(self):
        return not self.process.terminated()

# vim: expandtab tabstop=4 shiftwidth=4
