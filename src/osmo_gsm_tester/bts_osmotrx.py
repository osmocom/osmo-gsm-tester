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
import tempfile
from . import log, config, util, template, process, event_loop

class OsmoBtsTrx(log.Origin):
    suite_run = None
    bsc = None
    run_dir = None
    inst = None
    env = None
    trx = None
    pcu_sk_tmp_dir = None
    lac = None
    cellid = None
    proc_bts = None

    BIN_BTS_TRX = 'osmo-bts-trx'
    BIN_PCU = 'osmo-pcu'

    CONF_BTS_TRX = 'osmo-bts-trx.cfg'

    def __init__(self, suite_run, conf):
        super().__init__(log.C_RUN, OsmoBtsTrx.BIN_BTS_TRX)
        self.suite_run = suite_run
        self.conf = conf
        self.env = {}
        self.pcu_sk_tmp_dir = tempfile.mkdtemp('', 'ogtpcusk')
        if len(self.pcu_socket_path().encode()) > 107:
            raise log.Error('Path for pcu socket is longer than max allowed len for unix socket path (107):', self.pcu_socket_path())

    def cleanup(self):
        if self.pcu_sk_tmp_dir:
            try:
                os.remove(self.pcu_socket_path())
            except OSError:
                pass
            os.rmdir(self.pcu_sk_tmp_dir)

    def pcu_socket_path(self):
        return os.path.join(self.pcu_sk_tmp_dir, 'pcu_bts')

    def remote_addr(self):
        return self.conf.get('addr')

    def trx_remote_ip(self):
        conf_ip = self.conf.get('trx_remote_ip', None)
        if conf_ip is not None:
            return conf_ip
        # if 'trx_remote_ip' is not configured, use same IP as BTS
        return self.remote_addr()

    def launch_trx_enabled(self):
        return util.str2bool(self.conf.get('launch_trx'))

    def start(self):
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be started')
        self.suite_run.poll()

        self.log('Starting to connect to', self.bsc)
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        if self.launch_trx_enabled():
            self.trx = OsmoTrx(self.suite_run, self.trx_remote_ip(), self.remote_addr())
            self.trx.start()
            self.log('Waiting for osmo-trx to start up...')
            event_loop.wait(self, self.trx.trx_ready)

        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-bts')))
        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % self.inst)
        self.env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.proc_bts = self.launch_process(OsmoBtsTrx.BIN_BTS_TRX, '-r', '1',
                            '-c', os.path.abspath(self.config_file),
                            '-i', self.bsc.addr())
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
                            'trx_local_ip': self.remote_addr(),
                            'trx_remote_ip': self.trx_remote_ip(),
                            'pcu_socket_path': self.pcu_socket_path(),
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
        if self.lac is not None:
            config.overlay(values, { 'location_area_code': self.lac })
        if self.cellid is not None:
            config.overlay(values, { 'cell_identity': self.cellid })
        config.overlay(values, self.conf)
        self.dbg(conf=values)
        return values

    def ready_for_pcu(self):
        if not self.proc_bts or not self.proc_bts.is_running:
            return False
        return 'BTS is up' in (self.proc_bts.get_stderr() or '')

    def set_bsc(self, bsc):
        self.bsc = bsc

    def set_lac(self, lac):
        self.lac = lac

    def set_cellid(self, cellid):
        self.cellid = cellid

class OsmoTrx(log.Origin):
    suite_run = None
    run_dir = None
    inst = None
    env = None
    proc_trx = None

    BIN_TRX = 'osmo-trx'

    def __init__(self, suite_run, listen_ip, bts_ip):
        super().__init__(log.C_RUN, OsmoTrx.BIN_TRX)
        self.suite_run = suite_run
        self.env = {}
        self.listen_ip = listen_ip
        self.bts_ip = bts_ip

    def start(self):
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst(OsmoTrx.BIN_TRX)))
        lib = self.inst.child('lib')
        self.env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }
        self.proc_trx = self.launch_process(OsmoTrx.BIN_TRX, '-x', '-j', self.listen_ip, '-i', self.bts_ip)

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
