# osmo_gsm_tester: specifics for running a osmo-bts-oc2g
#
# Copyright (C) 2019 by sysmocom - s.f.m.c. GmbH
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
from . import log, config, util, template, process, pcu_oc2g, bts_osmo

class OsmoBtsOC2G(bts_osmo.OsmoBts):
##############
# PROTECTED
##############

    REMOTE_DIR = '/osmo-gsm-tester-bts'
    BTS_OC2G_BIN = 'osmo-bts-oc2g'
    BTS_OC2G_CFG = 'osmo-bts-oc2g.cfg'

    def __init__(self, suite_run, conf):
        super().__init__(suite_run, conf, OsmoBtsOC2G.BTS_OC2G_BIN, 'osmo_bts_oc2g')
        self.run_dir = None
        self.inst = None
        self.remote_inst = None
        self.remote_dir = None
        self.remote_user = 'root'

    def _direct_pcu_enabled(self):
        return util.str2bool(self.conf.get('direct_pcu'))

    def create_pcu(self):
        return pcu_oc2g.OsmoPcuOC2G(self.suite_run, self, self.conf)

    def configure(self):
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be configured')

        self.config_file = self.run_dir.new_file(OsmoBtsOC2G.BTS_OC2G_CFG)
        self.dbg(config_file=self.config_file)

        values = { 'osmo_bts_oc2g': config.get_defaults('osmo_bts_oc2g') }
        config.overlay(values, self.suite_run.config())
        config.overlay(values, {
                        'osmo_bts_oc2g': {
                            'oml_remote_ip': self.bsc.addr(),
                            'pcu_socket_path': self.pcu_socket_path(),
                        }
        })
        config.overlay(values, { 'osmo_bts_oc2g': self.conf })

        self.dbg('OSMO-BTS-OC2G CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(OsmoBtsOC2G.BTS_OC2G_CFG, values)
            self.dbg(r)
            f.write(r)

########################
# PUBLIC - INTERNAL API
########################
    def pcu_socket_path(self):
        return os.path.join(OsmoBtsOC2G.REMOTE_DIR, 'pcu_bts')

    def conf_for_bsc(self):
        values = self.conf_for_bsc_prepare()
        # Hack until we have proper ARFCN resource allocation support (OS#2230)
        band = values.get('band')
        trx_list = values.get('trx_list')
        if band == 'GSM-900':
            for trx_i in range(len(trx_list)):
                config.overlay(trx_list[trx_i], { 'arfcn' : str(50 + trx_i * 2) })
        self.dbg(conf=values)
        return values

###################
# PUBLIC (test API included)
###################
    # We get log from ssh stdout instead of usual stderr.
    def ready_for_pcu(self):
        if not self.proc_bts or not self.proc_bts.is_running:
            return False
        return 'BTS is up' in (self.proc_bts.get_stdout() or '')

    def start(self, keepalive=False):
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be started')
        log.log('Starting OsmoBtsOC2G to connect to', self.bsc)
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst(OsmoBtsOC2G.BTS_OC2G_BIN)))
        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in', self.inst)
        if not self.inst.isfile('bin', OsmoBtsOC2G.BTS_OC2G_BIN):
            raise log.Error('No osmo-bts-oc2g binary in', self.inst)

        rem_host = remote.RemoteHost(self.run_dir, self.remote_user, self.remote_addr())
        remote_prefix_dir = util.Dir(OsmoBtsOC2G.REMOTE_DIR)
        self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
        remote_run_dir = util.Dir(remote_prefix_dir.child(OsmoBtsOC2G.BTS_OC2G_BIN))
        remote_config_file = remote_run_dir.child(OsmoBtsOC2G.BTS_OC2G_CFG)

        rem_host.recreate_remote_dir(self.remote_inst)
        rem_host.scp('scp-inst-to-remote', str(self.inst), remote_prefix_dir)
        rem_host.create_remote_dir(remote_run_dir)
        rem_host.scp('scp-cfg-to-remote', self.config_file, remote_config_file)

        remote_lib = self.remote_inst.child('lib')
        remote_binary = self.remote_inst.child('bin', OsmoBtsOC2G.BTS_OC2G_BIN)
        args = ('LD_LIBRARY_PATH=%s' % remote_lib,
         remote_binary, '-c', remote_config_file, '-r', '1',
         '-i', self.bsc.addr())

        if self._direct_pcu_enabled():
            args += ('-M',)

        proc = rem_host.RemoteProcess(OsmoBtsOC2G.BTS_OC2G_BIN, args)
        self.suite_run.remember_to_stop(proc, keepalive)
        proc.launch()
# vim: expandtab tabstop=4 shiftwidth=4
