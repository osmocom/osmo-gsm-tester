# osmo_gsm_tester: specifics for running an osmo-bts-virtual
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
# Copyright (C) 2018 Holger Hans Peter Freyther
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
from ..core import config, util, template, process
from . import bts_osmo

class OsmoBtsVirtual(bts_osmo.OsmoBtsMainUnit):
##############
# PROTECTED
##############

    BIN_BTS = 'osmo-bts-virtual'
    BIN_PCU = 'osmo-pcu'

    CONF_BTS = 'osmo-bts-virtual.cfg'

    def __init__(self, testenv, conf):
        """Initializes the OsmoBtsVirtual."""
        super().__init__(testenv, conf, OsmoBtsVirtual.BIN_BTS, 'osmo_bts_virtual')
        self.run_dir = None
        self.inst = None
        self.env = {}

    def launch_process(self, keepalive, binary_name, *args):
        """Launches the osmo-bts-virtual process."""

        binary = os.path.abspath(self.inst.child('bin', binary_name))
        run_dir = self.run_dir.new_dir(binary_name)
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        proc = process.Process(binary_name, run_dir,
                               (binary,) + args,
                               env=self.env)
        self.testenv.remember_to_stop(proc, keepalive)
        proc.launch()
        return proc

    def configure(self):
        """Builds the configuration for osmo-bts-virtual and writes it to a file."""

        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be configured')
        self.config_file = self.run_dir.new_file(OsmoBtsVirtual.CONF_BTS)
        self.dbg(config_file=self.config_file)

        values = dict(osmo_bts_virtual=config.get_defaults('osmo_bts_virtual'))
        config.overlay(values, self.testenv.suite().config())
        config.overlay(values, {
                        'osmo_bts_virtual': {
                            'oml_remote_ip': self.bsc.addr(),
                            'pcu_socket_path': self.pcu_socket_path(),
                        }
        })
        config.overlay(values, { 'osmo_bts_virtual': self.conf })

        self.dbg('OSMO-BTS-VIRTUAL CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(OsmoBtsVirtual.CONF_BTS, values)
            self.dbg(r)
            f.write(r)

########################
# PUBLIC - INTERNAL API
########################
    def conf_for_bsc(self):
        """Returns the configuration for the BSC (including the BSC/NITB IP)."""
        values = self.conf_for_bsc_prepare()
        self.dbg(conf=values)
        return values

###################
# PUBLIC (test API included)
###################
    def start(self, keepalive=False):
        """Handles starting/turning-up the osmo-bts-virtual process."""
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be started')
        self.testenv.poll()

        self.log('Starting to connect to', self.bsc)
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()

        self.inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('osmo-bts')))
        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % self.inst)
        self.env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.proc_bts = self.launch_process(keepalive, OsmoBtsVirtual.BIN_BTS, '-r', '1',
                            '-c', os.path.abspath(self.config_file),
                            '-i', self.bsc.addr())
        self.testenv.poll()

# vim: expandtab tabstop=4 shiftwidth=4
