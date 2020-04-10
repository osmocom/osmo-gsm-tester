# osmo_gsm_tester: specifics for running an openggsn
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

from .core import log, util, config, template, process
from . import pcap_recorder

class OsmoGgsn(log.Origin):

    def __init__(self, suite_run, ip_address):
        super().__init__(log.C_RUN, 'osmo-ggsn_%s' % ip_address.get('addr'))
        self.run_dir = None
        self.config_file = None
        self.process = None
        self.suite_run = suite_run
        self.ip_address = ip_address

    def start(self):
        self.log('Starting osmo-ggsn')
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-ggsn')))

        binary = inst.child('bin', 'osmo-ggsn')
        if not os.path.isfile(binary):
            raise log.Error('Binary missing:', binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in', inst)

        pcap_recorder.PcapRecorder(self.suite_run, self.run_dir.new_dir('pcap'), None,
                                   'host %s' % self.addr())

        env = {}

        # setting capabilities will later disable use of LD_LIBRARY_PATH from ELF loader -> modify RPATH instead.
        self.log('Setting RPATH for osmo-ggsn')
        util.change_elf_rpath(binary, util.prepend_library_path(lib), self.run_dir.new_dir('patchelf'))
        # osmo-ggsn requires CAP_NET_ADMIN to create tunnel devices: ioctl(TUNSETIFF):
        self.log('Applying CAP_NET_ADMIN capability to osmo-ggsn')
        util.setcap_net_admin(binary, self.run_dir.new_dir('setcap_net_admin'))

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        self.process = process.Process(self.name(), self.run_dir,
                                       (binary,
                                        '-c', os.path.abspath(self.config_file)),
                                       env=env)
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def configure(self):
        self.config_file = self.run_dir.new_file('osmo-ggsn.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(ggsn=config.get_defaults('ggsn'))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, dict(ggsn=dict(ip_address=self.ip_address)))
        config.overlay(values, dict(ggsn=dict(statedir=self.run_dir.new_dir('statedir'))))

        self.dbg('GGSN CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-ggsn.cfg', values)
            self.dbg(r)
            f.write(r)

    def conf_for_client(self):
        return dict(ggsn=dict(ip_address=self.ip_address))

    def addr(self):
        return self.ip_address.get('addr')

    def running(self):
        return not self.process.terminated()

# vim: expandtab tabstop=4 shiftwidth=4
