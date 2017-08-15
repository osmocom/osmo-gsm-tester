# osmo_gsm_tester: specifics for running an osmo-bts-trx
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
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
from . import log, config, util, template, process, event_loop

class OsmoBtsTrx(log.Origin):
    suite_run = None
    bsc = None
    run_dir = None
    inst = None
    env = None
    trx = None

    BIN_BTS_TRX = 'osmo-bts-trx'
    BIN_PCU = 'osmo-pcu'

    CONF_BTS_TRX = 'osmo-bts-trx.cfg'

    def __init__(self, suite_run, conf):
        super().__init__(log.C_RUN, OsmoBtsTrx.BIN_BTS_TRX)
        self.suite_run = suite_run
        self.conf = conf
        self.env = {}

    def remote_addr(self):
        # FIXME
        return '127.0.0.1'

    def start(self):
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be started')
        self.suite_run.poll()

        self.log('Starting to connect to', self.bsc)
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        self.trx = OsmoTrx(self.suite_run)
        self.trx.start()
        self.log('Waiting for osmo-trx to start up...')
        event_loop.wait(self, self.trx.trx_ready)

        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst(OsmoBtsTrx.BIN_BTS_TRX)))
        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % self.inst)
        self.env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.launch_process(OsmoBtsTrx.BIN_BTS_TRX, '-r', '1',
                            '-c', os.path.abspath(self.config_file),
                            '-i', self.bsc.addr())
        #self.launch_process(OsmoBtsTrx.BIN_PCU, '-r', '1')
        self.suite_run.poll()

    def launch_process(self, binary_name, *args):
        binary = os.path.abspath(self.inst.child('bin', binary_name))
        run_dir = self.run_dir.new_dir(binary_name)
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        proc = process.Process(binary_name, run_dir,
                               (binary,) + args,
                               env=self.env)
        self.suite_run.remember_to_stop(proc)
        proc.launch()
        return proc

    def configure(self):
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be configured')
        self.config_file = self.run_dir.new_file(OsmoBtsTrx.CONF_BTS_TRX)
        self.dbg(config_file=self.config_file)

        values = dict(osmo_bts_trx=config.get_defaults('osmo_bts_trx'))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, {
                        'osmo_bts_trx': {
                            'oml_remote_ip': self.bsc.addr(),
                            'pcu_socket_path': os.path.join(str(self.run_dir), 'pcu_bts')
                        }
        })
        config.overlay(values, { 'osmo_bts_trx': self.conf })

        self.dbg('OSMO-BTS-TRX CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(OsmoBtsTrx.CONF_BTS_TRX, values)
            self.dbg(r)
            f.write(r)

    def conf_for_bsc(self):
        values = config.get_defaults('bsc_bts')
        config.overlay(values, config.get_defaults('osmo_bts_trx'))
        config.overlay(values, self.conf)
        self.dbg(conf=values)
        return values

    def set_bsc(self, bsc):
        self.bsc = bsc

class OsmoTrx(log.Origin):
    suite_run = None
    run_dir = None
    inst = None
    env = None
    proc_trx = None

    BIN_TRX = 'osmo-trx'

    def __init__(self, suite_run):
        super().__init__(log.C_RUN, OsmoTrx.BIN_TRX)
        self.suite_run = suite_run
        self.env = {}

    def start(self):
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst(OsmoTrx.BIN_TRX)))
        self.proc_trx = self.launch_process(OsmoTrx.BIN_TRX, '-x')

    def launch_process(self, binary_name, *args):
        binary = os.path.abspath(self.inst.child('bin', binary_name))
        run_dir = self.run_dir.new_dir(binary_name)
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        proc = process.Process(binary_name, run_dir,
                               (binary,) + args,
                               env=self.env)
        self.suite_run.remember_to_stop(proc)
        proc.launch()
        return proc

    def trx_ready(self):
        if not self.proc_trx or not self.proc_trx.is_running:
            return False
        return '-- Transceiver active with' in (self.proc_trx.get_stdout() or '')
# vim: expandtab tabstop=4 shiftwidth=4
