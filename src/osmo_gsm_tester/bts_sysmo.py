# osmo_gsm_tester: specifics for running a sysmoBTS
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
from . import log, config, util, template, process, pcu_sysmo, bts_osmo

class SysmoBts(bts_osmo.OsmoBts):
##############
# PROTECTED
##############

    REMOTE_DIR = '/osmo-gsm-tester-bts'
    BTS_SYSMO_BIN = 'osmo-bts-sysmo'
    BTS_SYSMO_CFG = 'osmo-bts-sysmo.cfg'

    def __init__(self, suite_run, conf):
        super().__init__(suite_run, conf, SysmoBts.BTS_SYSMO_BIN, 'osmo_bts_sysmo')
        self.run_dir = None
        self.inst = None
        self.remote_inst = None
        self.remote_dir = None
        self.remote_user = 'root'

    def _direct_pcu_enabled(self):
        return util.str2bool(self.conf.get('direct_pcu'))

    def launch_remote(self, name, popen_args, remote_cwd=None, keepalive=False):
        run_dir = self.run_dir.new_dir(name)
        proc = process.RemoteProcess(name, run_dir, self.remote_user, self.remote_addr(), remote_cwd,
                                     popen_args)
        self.suite_run.remember_to_stop(proc, keepalive)
        proc.launch()
        return proc

    def create_pcu(self):
        return pcu_sysmo.OsmoPcuSysmo(self.suite_run, self, self.conf)

    def configure(self):
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be configured')

        self.config_file = self.run_dir.new_file(SysmoBts.BTS_SYSMO_CFG)
        self.dbg(config_file=self.config_file)

        values = { 'osmo_bts_sysmo': config.get_defaults('osmo_bts_sysmo') }
        config.overlay(values, self.suite_run.config())
        config.overlay(values, {
                        'osmo_bts_sysmo': {
                            'oml_remote_ip': self.bsc.addr(),
                            'pcu_socket_path': self.pcu_socket_path(),
                        }
        })
        config.overlay(values, { 'osmo_bts_sysmo': self.conf })

        self.dbg('SYSMOBTS CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(SysmoBts.BTS_SYSMO_CFG, values)
            self.dbg(r)
            f.write(r)

########################
# PUBLIC - INTERNAL API
########################
    def pcu_socket_path(self):
        return os.path.join(SysmoBts.REMOTE_DIR, 'pcu_bts')

    def conf_for_bsc(self):
        values = self.conf_for_bsc_prepare()
        self.dbg(conf=values)
        return values

###################
# PUBLIC (test API included)
###################
    def start(self, keepalive=False):
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be started')
        log.log('Starting sysmoBTS to connect to', self.bsc)
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst(SysmoBts.BTS_SYSMO_BIN)))
        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in', self.inst)
        if not self.inst.isfile('bin', SysmoBts.BTS_SYSMO_BIN):
            raise log.Error('No osmo-bts-sysmo binary in', self.inst)

        remote_run_dir = util.Dir(SysmoBts.REMOTE_DIR)

        self.remote_inst = process.copy_inst_ssh(self.run_dir, self.inst, remote_run_dir, self.remote_user,
                                         self.remote_addr(), SysmoBts.BTS_SYSMO_BIN, self.config_file)
        process.run_remote_sync(self.run_dir, self.remote_user, self.remote_addr(), 'reload-dsp-firmware',
                             ('/bin/sh', '-c', '"cat /lib/firmware/sysmobts-v?.bit > /dev/fpgadl_par0 ; cat /lib/firmware/sysmobts-v?.out > /dev/dspdl_dm644x_0"'))

        remote_config_file = remote_run_dir.child(SysmoBts.BTS_SYSMO_CFG)
        remote_lib = self.remote_inst.child('lib')
        remote_binary = self.remote_inst.child('bin', 'osmo-bts-sysmo')

        args = ('LD_LIBRARY_PATH=%s' % remote_lib,
         remote_binary, '-c', remote_config_file, '-r', '1',
         '-i', self.bsc.addr())

        if self._direct_pcu_enabled():
            args += ('-M',)

        self.proc_bts = self.launch_remote('osmo-bts-sysmo', args, remote_cwd=remote_run_dir, keepalive=keepalive)

# vim: expandtab tabstop=4 shiftwidth=4
