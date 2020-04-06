# osmo_gsm_tester: specifics for running a osmo-pcu for sysmoBTS
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
from . import log, config, util, template, process

class OsmoPcuSysmo(log.Origin):

    REMOTE_DIR = '/osmo-gsm-tester-pcu'
    PCU_SYSMO_BIN = 'osmo-pcu'
    PCU_SYSMO_CFG = 'osmo-pcu-sysmo.cfg'

    def __init__(self, suite_run, sysmobts, conf):
        super().__init__(log.C_RUN, self.PCU_SYSMO_BIN)
        self.run_dir = None
        self.bsc = None
        self.inst = None
        self.remote_inst = None
        self.remote_dir = None
        self.sysmobts = None
        self.suite_run = suite_run
        self.sysmobts = sysmobts
        self.conf = conf
        self.remote_env = {}
        self.remote_user = 'root'

    def start(self, keepalive=False):
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-pcu-sysmo')))
        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in', self.inst)
        if not self.inst.isfile('bin', OsmoPcuSysmo.PCU_SYSMO_BIN):
            raise log.Error('No osmo-pcu-sysmo binary in', self.inst)

        self.remote_dir = util.Dir(OsmoPcuSysmo.REMOTE_DIR)
        self.remote_inst = util.Dir(self.remote_dir.child(os.path.basename(str(self.inst))))

        self.run_remote('rm-remote-dir', ('test', '!', '-d', OsmoPcuSysmo.REMOTE_DIR, '||', 'rm', '-rf', OsmoPcuSysmo.REMOTE_DIR))
        self.run_remote('mk-remote-dir', ('mkdir', '-p', OsmoPcuSysmo.REMOTE_DIR))
        self.run_local('scp-inst-to-sysmobts',
            ('scp', '-r', str(self.inst), '%s@%s:%s' % (self.remote_user, self.sysmobts.remote_addr(), str(self.remote_inst))))

        remote_run_dir = self.remote_dir.child(OsmoPcuSysmo.PCU_SYSMO_BIN)
        self.run_remote('mk-remote-run-dir', ('mkdir', '-p', remote_run_dir))

        remote_config_file = self.remote_dir.child(OsmoPcuSysmo.PCU_SYSMO_CFG)
        self.run_local('scp-cfg-to-sysmobts',
            ('scp', '-r', self.config_file, '%s@%s:%s' % (self.remote_user, self.sysmobts.remote_addr(), remote_config_file)))

        remote_lib = self.remote_inst.child('lib')
        remote_binary = self.remote_inst.child('bin', OsmoPcuSysmo.PCU_SYSMO_BIN)
        self.launch_remote(OsmoPcuSysmo.PCU_SYSMO_BIN,
            ('LD_LIBRARY_PATH=%s' % remote_lib,
             remote_binary, '-c', remote_config_file, '-r', '1',
             '-i', self.sysmobts.bsc.addr()),
            remote_cwd=remote_run_dir, keepalive=keepalive)

    def _process_remote(self, name, popen_args, remote_cwd=None):
        run_dir = self.run_dir.new_dir(name)
        return process.RemoteProcess(name, run_dir, self.remote_user, self.sysmobts.remote_addr(), remote_cwd,
                                     popen_args)

    def run_remote(self, name, popen_args, remote_cwd=None):
        proc = self._process_remote(name, popen_args, remote_cwd)
        proc.launch()
        proc.wait()
        if proc.result != 0:
            log.ctx(proc)
            raise log.Error('Exited in error')

    def launch_remote(self, name, popen_args, remote_cwd=None, keepalive=False):
        proc = self._process_remote(name, popen_args, remote_cwd)
        self.suite_run.remember_to_stop(proc, keepalive)
        proc.launch()

    def run_local(self, name, popen_args):
        run_dir = self.run_dir.new_dir(name)
        proc = process.Process(name, run_dir, popen_args)
        proc.launch()
        proc.wait()
        if proc.result != 0:
            log.ctx(proc)
            raise log.Error('Exited in error')

    def configure(self):
        self.config_file = self.run_dir.new_file(OsmoPcuSysmo.PCU_SYSMO_CFG)
        self.dbg(config_file=self.config_file)

        values = { 'osmo_pcu_sysmo': config.get_defaults('osmo_pcu_sysmo') }
        config.overlay(values, self.suite_run.config())
        config.overlay(values, {
                        'osmo_pcu_sysmo': {
                            'bts_addr': self.sysmobts.remote_addr(),
                            'pcu_socket_path': self.sysmobts.pcu_socket_path(),
                            'egprs_enabled': self.egprs_enabled(),
                        }
        })
        config.overlay(values, { 'osmo_pcu_sysmo': self.conf })

        self.dbg('OSMO-PCU-SYSMO CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(OsmoPcuSysmo.PCU_SYSMO_CFG, values)
            self.dbg(r)
            f.write(r)

# vim: expandtab tabstop=4 shiftwidth=4
