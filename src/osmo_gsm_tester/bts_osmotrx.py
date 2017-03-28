# osmo_gsm_tester: specifics for running a sysmoBTS
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
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
from . import log, config, util, template, process

class OsmoBtsTrx(log.Origin):
    suite_run = None
    nitb = None
    run_dir = None
    processes = None
    inst = None
    env = None

    BIN_TRX = 'osmo-trx'
    BIN_BTS_TRX = 'osmo-bts-trx'
    BIN_PCU = 'osmo-pcu'

    def __init__(self, suite_run, conf):
        self.suite_run = suite_run
        self.conf = conf
        self.set_name('osmo-bts-trx')
        self.set_log_category(log.C_RUN)
        self.processes = {}
        self.inst = None
        self.env = {}

    def start(self):
        if self.nitb is None:
            raise RuntimeError('BTS needs to be added to a NITB before it can be started')
        self.suite_run.poll()

        self.log('Starting to connect to', self.nitb)
        self.run_dir = util.Dir(self.suite_run.trial.get_run_dir().new_dir(self.name()))
        self.configure()

        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-bts-trx')))
        self.env = { 'LD_LIBRARY_PATH': str(self.inst) }

        self.launch_process(OsmoBtsTrx.BIN_TRX)
        self.launch_process(OsmoBtsTrx.BIN_BTS_TRX, '-r', '1', '-c', os.path.abspath(self.config_file))
        #self.launch_process(OsmoBtsTrx.BIN_PCU, '-r', '1')
        self.suite_run.poll()

    def launch_process(self, binary_name, *args):
        if self.processes.get(binary_name) is not None:
            raise RuntimeError('Attempt to launch twice: %r' % binary_name)

        binary = os.path.abspath(self.inst.child('bin', binary_name))
        run_dir = self.run_dir.new_dir(binary_name)
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        proc = process.Process(binary_name, run_dir,
                               (binary,) + args,
                               env=self.env)
        self.processes[binary_name] = proc
        self.suite_run.remember_to_stop(proc)
        proc.launch()

    def configure(self):
        if self.nitb is None:
            raise RuntimeError('BTS needs to be added to a NITB before it can be configured')
        self.config_file = self.run_dir.new_file('osmo-bts-trx.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(osmo_bts_trx=config.get_defaults('osmo_bts_trx'))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, dict(osmo_bts_trx=dict(oml_remote_ip=self.nitb.addr())))
        config.overlay(values, dict(osmo_bts_trx=self.conf))
        self.dbg(conf=values)

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-bts-trx.cfg', values)
            self.dbg(r)
            f.write(r)

    def conf_for_nitb(self):
        values = config.get_defaults('nitb_bts')
        config.overlay(values, config.get_defaults('osmo_bts_sysmo'))
        config.overlay(values, self.conf)
        config.overlay(values, { 'type': 'sysmobts' })
        self.dbg(conf=values)
        return values

    def set_nitb(self, nitb):
        self.nitb = nitb

# vim: expandtab tabstop=4 shiftwidth=4
