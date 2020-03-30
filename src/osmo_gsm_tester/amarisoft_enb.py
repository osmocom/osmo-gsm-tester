# osmo_gsm_tester: specifics for running an SRS eNodeB process
#
# Copyright (C) 2020 by sysmocom - s.f.m.c. GmbH
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

from . import log, util, config, template, process, remote
from . import enb

def rf_type_valid(rf_type_str):
    return rf_type_str in ('uhd')

#reference: srsLTE.git srslte_symbol_sz()
def num_prb2symbol_sz(num_prb):
    if num_prb <= 6:
        return 128
    if num_prb <= 15:
        return 256
    if num_prb <= 25:
        return 384
    if num_prb <= 50:
        return 768
    if num_prb <= 75:
        return 1024
    if num_prb <= 110:
        return 1536
    raise log.Error('invalid num_prb %r', num_prb)

def num_prb2base_srate(num_prb):
    return num_prb2symbol_sz(num_prb) * 15 * 1000

class AmarisoftENB(enb.eNodeB):

    REMOTE_DIR = '/osmo-gsm-tester-amarisoftenb'
    BINFILE = 'lteenb'
    CFGFILE = 'amarisoft_enb.cfg'
    CFGFILE_SIB1 = 'amarisoft_sib1.asn'
    CFGFILE_SIB23 = 'amarisoft_sib23.asn'
    CFGFILE_RF = 'amarisoft_rf_driver.cfg'
    CFGFILE_DRB = 'amarisoft_drb.cfg'
    LOGFILE = 'lteenb.log'

    def __init__(self, suite_run, conf):
        super().__init__(suite_run, conf, 'amarisoftenb')
        self.ue = None
        self.epc = None
        self.run_dir = None
        self._bin_prefix = None
        self.config_file = None
        self.config_sib1_file = None
        self.config_sib23_file = None
        self.config_rf_file = None
        self.config_drb_file = None
        self.log_file = None
        self.process = None
        self.rem_host = None
        self.remote_config_file =  None
        self.remote_config_sib1_file = None
        self.remote_config_sib23_file = None
        self.remote_config_rf_file = None
        self.remote_config_drb_file = None
        self.remote_log_file = None
        self._num_prb = 0
        self._txmode = 0
        self.suite_run = suite_run
        self.remote_user = conf.get('remote_user', None)
        if not rf_type_valid(conf.get('rf_dev_type', None)):
            raise log.Error('Invalid rf_dev_type=%s' % conf.get('rf_dev_type', None))

    def bin_prefix(self):
        if self._bin_prefix is None:
            self._bin_prefix = os.getenv('AMARISOFT_PATH_ENB', AmarisoftENB.REMOTE_DIR)
        return self._bin_prefix

    def cleanup(self):
        if self.process is None:
            return
        if self.setup_runs_locally():
            return
        # copy back files (may not exist, for instance if there was an early error of process):
        try:
            self.rem_host.scpfrom('scp-back-log', self.remote_log_file, self.log_file)
        except Exception as e:
            self.log(repr(e))


    def setup_runs_locally(self):
        return self.remote_user is None

    def start(self, epc):
        self.log('Starting AmarisoftENB')
        self.epc = epc
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()
        self._start()

        # send t+Enter to enable console trace
        self.dbg('Enabling console trace')
        self.process.stdin_write('t\n')

    def _start(self):
        if self.setup_runs_locally():
            env = { 'LD_LIBRARY_PATH': util.prepend_library_path(self.inst) }
            binary = self.inst.child('.', AmarisoftENB.BINFILE)
            self.dbg(run_dir=self.run_dir, binary=binary, env=env)
            args = (binary, os.path.abspath(self.config_file))
            self.process = process.Process(self.name(), self.run_dir, args, env=env)
        else:
            remote_env = { 'LD_LIBRARY_PATH': self.remote_inst }
            remote_binary = self.remote_inst.child('', AmarisoftENB.BINFILE)
            args = (remote_binary, self.remote_config_file)
            self.process = self.rem_host.RemoteProcess(AmarisoftENB.BINFILE, args, remote_env=remote_env)

        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def gen_conf_file(self, path, filename, values):
        self.dbg('AmarisoftENB ' + filename + ':\n' + pprint.pformat(values))
        with open(path, 'w') as f:
            r = template.render(filename, values)
            self.dbg(r)
            f.write(r)

    def configure(self):

        self.inst = util.Dir(os.path.abspath(self.bin_prefix()))
        lib = self.inst.child('lib')
        if not self.inst.isfile('', AmarisoftENB.BINFILE):
            raise log.Error('No %s binary in' % AmarisoftENB.BINFILE, self.inst)

        self.config_file = self.run_dir.child(AmarisoftENB.CFGFILE)
        self.config_sib1_file = self.run_dir.child(AmarisoftENB.CFGFILE_SIB1)
        self.config_sib23_file = self.run_dir.child(AmarisoftENB.CFGFILE_SIB23)
        self.config_rf_file = self.run_dir.child(AmarisoftENB.CFGFILE_RF)
        self.config_drb_file = self.run_dir.child(AmarisoftENB.CFGFILE_DRB)
        self.log_file = self.run_dir.child(AmarisoftENB.LOGFILE)

        if not self.setup_runs_locally():
            self.rem_host = remote.RemoteHost(self.run_dir, self.remote_user, self._addr)
            remote_prefix_dir = util.Dir(AmarisoftENB.REMOTE_DIR)
            self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
            remote_run_dir = util.Dir(remote_prefix_dir.child(AmarisoftENB.BINFILE))

            self.remote_config_file = remote_run_dir.child(AmarisoftENB.CFGFILE)
            self.remote_config_sib1_file = remote_run_dir.child(AmarisoftENB.CFGFILE_SIB1)
            self.remote_config_sib23_file = remote_run_dir.child(AmarisoftENB.CFGFILE_SIB23)
            self.remote_config_rf_file = remote_run_dir.child(AmarisoftENB.CFGFILE_RF)
            self.remote_config_drb_file = remote_run_dir.child(AmarisoftENB.CFGFILE_DRB)
            self.remote_log_file = remote_run_dir.child(AmarisoftENB.LOGFILE)

        values = dict(enb=config.get_defaults('enb'))
        config.overlay(values, dict(enb=config.get_defaults('amarisoftenb')))
        config.overlay(values, dict(enb=self.suite_run.config().get('enb', {})))
        config.overlay(values, dict(enb=self._conf))
        config.overlay(values, dict(enb={ 'mme_addr': self.epc.addr() }))

        self._num_prb = int(values['enb'].get('num_prb', None))
        assert self._num_prb
        self._txmode = int(values['enb'].get('transmission_mode', None))
        assert self._txmode
        self._num_cells = int(values['enb'].get('num_cells', None))
        assert self._num_cells
        config.overlay(values, dict(enb={ 'num_ports': self.num_ports() }))

        logfile = self.log_file if self.setup_runs_locally() else self.remote_log_file
        config.overlay(values, dict(enb=dict(log_filename=logfile)))

        self.gen_conf_file(self.config_file, AmarisoftENB.CFGFILE, values)
        self.gen_conf_file(self.config_sib1_file, AmarisoftENB.CFGFILE_SIB1, values)
        self.gen_conf_file(self.config_sib23_file, AmarisoftENB.CFGFILE_SIB23, values)
        self.gen_conf_file(self.config_rf_file, AmarisoftENB.CFGFILE_RF, values)
        self.gen_conf_file(self.config_drb_file, AmarisoftENB.CFGFILE_DRB, values)

        if not self.setup_runs_locally():
            self.rem_host.recreate_remote_dir(self.remote_inst)
            self.rem_host.scp('scp-inst-to-remote', str(self.inst), remote_prefix_dir)
            self.rem_host.recreate_remote_dir(remote_run_dir)
            self.rem_host.scp('scp-cfg-to-remote', self.config_file, self.remote_config_file)
            self.rem_host.scp('scp-cfg-sib1-to-remote', self.config_sib1_file, self.remote_config_sib1_file)
            self.rem_host.scp('scp-cfg-sib23-to-remote', self.config_sib23_file, self.remote_config_sib23_file)
            self.rem_host.scp('scp-cfg-rr-to-remote', self.config_rf_file, self.remote_config_rf_file)
            self.rem_host.scp('scp-cfg-drb-to-remote', self.config_drb_file, self.remote_config_drb_file)

    def ue_add(self, ue):
        if self.ue is not None:
            raise log.Error("More than one UE per ENB not yet supported (ZeroMQ)")
        self.ue = ue

    def running(self):
        return not self.process.terminated()

    def num_prb(self):
        return self._num_prb

    def num_ports(self):
        if self._txmode == 1:
            return 1
        return 2

    def ue_max_rate(self, downlink=True):
        # The max rate for a single UE per PRB configuration in TM1
        max_phy_rate_tm1_dl = { 6 : 3.5e6,
                               15 : 11e6,
                               25 : 18e6,
                               50 : 36e6,
                               75 : 55e6,
                               100 : 75e6 }
        max_phy_rate_tm1_ul = { 6 : 0.9e6,
                               15 : 4.7e6,
                               25 : 10e6,
                               50 : 23e6,
                               75 : 34e6,
                               100 : 51e6 }
        if downlink:
            max_rate = max_phy_rate_tm1_dl[self.num_prb()]
        else:
            max_rate = max_phy_rate_tm1_ul[self.num_prb()]
        #TODO: calculate for non-standard prb numbers.
        if self._txmode > 2:
            max_rate *= 2
        # We use 3 control symbols for 6, 15 and 25 PRBs which results in lower max rate
        if self.num_prb() < 50:
          max_rate *= 0.9
        return max_rate

# vim: expandtab tabstop=4 shiftwidth=4
