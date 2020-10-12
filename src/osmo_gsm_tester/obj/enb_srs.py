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

from ..core import log, util, config, template, process, remote
from ..core.event_loop import MainLoop
from . import enb
from . import rfemu
from .srslte_common import srslte_common

from ..core import schema

def on_register_schemas():
    config_schema = {
        'enable_pcap': schema.BOOL_STR,
        'log_all_level': schema.STR,
        }
    schema.register_config_schema('enb', config_schema)

def rf_type_valid(rf_type_str):
    return rf_type_str in ('zmq', 'uhd', 'soapy', 'bladerf')

class srsENB(enb.eNodeB, srslte_common):

    REMOTE_DIR = '/osmo-gsm-tester-srsenb'
    BINFILE = 'srsenb'
    CFGFILE = 'srsenb.conf'
    CFGFILE_SIB = 'srsenb_sib.conf'
    CFGFILE_RR = 'srsenb_rr.conf'
    CFGFILE_DRB = 'srsenb_drb.conf'
    LOGFILE = 'srsenb.log'
    PCAPFILE = 'srsenb.pcap'

    def __init__(self, testenv, conf):
        super().__init__(testenv, conf, srsENB.BINFILE)
        srslte_common.__init__(self)
        self.ue = None
        self.run_dir = None
        self.gen_conf = None
        self.config_file = None
        self.config_sib_file = None
        self.config_rr_file = None
        self.config_drb_file = None
        self.log_file = None
        self.pcap_file = None
        self.process = None
        self.rem_host = None
        self.remote_run_dir = None
        self.remote_config_file =  None
        self.remote_config_sib_file = None
        self.remote_config_rr_file = None
        self.remote_config_drb_file = None
        self.remote_log_file = None
        self.remote_pcap_file = None
        self.enable_pcap = False
        self.metrics_file = None
        self.stop_sleep_time = 6 # We require at most 5s to stop
        self.testenv = testenv
        self.kpis = None
        self._additional_args = []
        if not rf_type_valid(conf.get('rf_dev_type', None)):
            raise log.Error('Invalid rf_dev_type=%s' % conf.get('rf_dev_type', None))

    def cleanup(self):
        if self.process is None:
            return
        if self._run_node.is_local():
            return

        # Make sure we give the UE time to tear down
        self.sleep_after_stop()

        # copy back files (may not exist, for instance if there was an early error of process):
        try:
            self.rem_host.scpfrom('scp-back-log', self.remote_log_file, self.log_file)
        except Exception as e:
            self.log(repr(e))
        if self.enable_pcap:
            try:
                self.rem_host.scpfrom('scp-back-pcap', self.remote_pcap_file, self.pcap_file)
            except Exception as e:
                self.log(repr(e))

        # Collect KPIs for each TC
        self.testenv.test().set_kpis(self.get_kpis())

    def start(self, epc):
        self.log('Starting srsENB')
        self._epc = epc
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()
        if self._run_node.is_local():
            self.start_locally()
        else:
            self.start_remotely()

        # send t+Enter to enable console trace
        self.dbg('Enabling console trace')
        self.process.stdin_write('t\n')

    def start_remotely(self):
        remote_env = { 'LD_LIBRARY_PATH': self.remote_inst.child('lib') }
        remote_binary = self.remote_inst.child('bin', srsENB.BINFILE)
        args = (remote_binary, self.remote_config_file)
        args += tuple(self._additional_args)

        self.process = self.rem_host.RemoteProcessSafeExit(srsENB.BINFILE, self.remote_run_dir, args, remote_env=remote_env, wait_time_sec=7)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def start_locally(self):
        binary = self.inst.child('bin', srsENB.BINFILE)
        lib = self.inst.child('lib')
        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }
        args = (binary, os.path.abspath(self.config_file))
        args += tuple(self._additional_args)

        self.process = process.Process(self.name(), self.run_dir, args, env=env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def gen_conf_file(self, path, filename, values):
        self.dbg('srsENB ' + filename + ':\n' + pprint.pformat(values))

        with open(path, 'w') as f:
            r = template.render(filename, values)
            self.dbg(r)
            f.write(r)

    def configure(self):
        self.inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('srslte',  self._run_node.run_label())))
        if not os.path.isdir(self.inst.child('lib')):
            raise log.Error('No lib/ in', self.inst)
        if not self.inst.isfile('bin', srsENB.BINFILE):
            raise log.Error('No %s binary in' % srsENB.BINFILE, self.inst)

        self.config_file = self.run_dir.child(srsENB.CFGFILE)
        self.config_sib_file = self.run_dir.child(srsENB.CFGFILE_SIB)
        self.config_rr_file = self.run_dir.child(srsENB.CFGFILE_RR)
        self.config_drb_file = self.run_dir.child(srsENB.CFGFILE_DRB)
        self.log_file = self.run_dir.child(srsENB.LOGFILE)
        self.pcap_file = self.run_dir.child(srsENB.PCAPFILE)

        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            remote_prefix_dir = util.Dir(srsENB.REMOTE_DIR)
            self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
            self.remote_run_dir = util.Dir(remote_prefix_dir.child(srsENB.BINFILE))

            self.remote_config_file = self.remote_run_dir.child(srsENB.CFGFILE)
            self.remote_config_sib_file = self.remote_run_dir.child(srsENB.CFGFILE_SIB)
            self.remote_config_rr_file = self.remote_run_dir.child(srsENB.CFGFILE_RR)
            self.remote_config_drb_file = self.remote_run_dir.child(srsENB.CFGFILE_DRB)
            self.remote_log_file = self.remote_run_dir.child(srsENB.LOGFILE)
            self.remote_pcap_file = self.remote_run_dir.child(srsENB.PCAPFILE)

        values = super().configure(['srsenb'])

        sibfile = self.config_sib_file if self._run_node.is_local() else self.remote_config_sib_file
        rrfile = self.config_rr_file if self._run_node.is_local() else self.remote_config_rr_file
        drbfile = self.config_drb_file if self._run_node.is_local() else self.remote_config_drb_file
        logfile = self.log_file if self._run_node.is_local() else self.remote_log_file
        pcapfile = self.pcap_file if self._run_node.is_local() else self.remote_pcap_file
        config.overlay(values, dict(enb=dict(sib_filename=sibfile,
                                             rr_filename=rrfile,
                                             drb_filename=drbfile,
                                             log_filename=logfile,
                                             pcap_filename=pcapfile,
                                             )))

        # Convert parsed boolean string to Python boolean:
        self.enable_pcap = util.str2bool(values['enb'].get('enable_pcap', 'false'))
        config.overlay(values, dict(enb={'enable_pcap': self.enable_pcap}))

        config.overlay(values, dict(enb={'enable_dl_awgn': util.str2bool(values['enb'].get('enable_dl_awgn', 'false'))}))
        config.overlay(values, dict(enb={'rf_dev_sync': values['enb'].get('rf_dev_sync', None)}))

        self._additional_args = []
        for add_args in values['enb'].get('additional_args', []):
            self._additional_args += add_args.split()

        # We need to set some specific variables programatically here to match IP addresses:
        if self._conf.get('rf_dev_type') == 'zmq':
            rf_dev_args = self.get_zmq_rf_dev_args()
            config.overlay(values, dict(enb=dict(rf_dev_args=rf_dev_args)))

        # Set UHD frame size as a function of the cell bandwidth on B2XX
        if self._conf.get('rf_dev_type') == 'uhd' and values['enb'].get('rf_dev_args', None) is not None:
            if 'b200' in values['enb'].get('rf_dev_args'):
                rf_dev_args = values['enb'].get('rf_dev_args', '')
                rf_dev_args += ',' if rf_dev_args != '' and not rf_dev_args.endswith(',') else ''

                if self._num_prb == 75:
                    rf_dev_args += 'master_clock_rate=15.36e6,'

                if self._txmode <= 2:
                    # SISO config
                    if self._num_prb < 25:
                        rf_dev_args += 'send_frame_size=512,recv_frame_size=512'
                    elif self._num_prb == 25:
                        rf_dev_args += 'send_frame_size=1024,recv_frame_size=1024'
                    else:
                        rf_dev_args += ''
                else:
                    # MIMO config
                    rf_dev_args += 'num_recv_frames=64,num_send_frames=64'
                    if self._num_prb > 50:
                        # Reduce over the wire format to sc12
                        rf_dev_args += ',otw_format=sc12'

                config.overlay(values, dict(enb=dict(rf_dev_args=rf_dev_args)))

        self.gen_conf = values

        self.gen_conf_file(self.config_file, srsENB.CFGFILE, values)
        self.gen_conf_file(self.config_sib_file, srsENB.CFGFILE_SIB, values)
        self.gen_conf_file(self.config_rr_file, srsENB.CFGFILE_RR, values)
        self.gen_conf_file(self.config_drb_file, srsENB.CFGFILE_DRB, values)

        if not self._run_node.is_local():
            self.rem_host.recreate_remote_dir(self.remote_inst)
            self.rem_host.scp('scp-inst-to-remote', str(self.inst), remote_prefix_dir)
            self.rem_host.recreate_remote_dir(self.remote_run_dir)
            self.rem_host.scp('scp-cfg-to-remote', self.config_file, self.remote_config_file)
            self.rem_host.scp('scp-cfg-sib-to-remote', self.config_sib_file, self.remote_config_sib_file)
            self.rem_host.scp('scp-cfg-rr-to-remote', self.config_rr_file, self.remote_config_rr_file)
            self.rem_host.scp('scp-cfg-drb-to-remote', self.config_drb_file, self.remote_config_drb_file)

    def ue_add(self, ue):
        if self.ue is not None:
            raise log.Error("More than one UE per ENB not yet supported (ZeroMQ)")
        self.ue = ue

    def running(self):
        return not self.process.terminated()

    def get_rfemu(self, cell=0, dl=True):
        cell_list = self.gen_conf['enb'].get('cell_list', None)
        if cell_list is None or len(cell_list) < cell + 1:
            raise log.Error('cell_list attribute or subitem not found!')
        rfemu_cfg = cell_list[cell].get('dl_rfemu', None)
        if rfemu_cfg is None:
            raise log.Error('rfemu attribute not found in cell_list item!')

        rfemu_obj = rfemu.get_instance_by_type(rfemu_cfg['type'], rfemu_cfg)
        return rfemu_obj

    def ue_max_rate(self, downlink=True, num_carriers=1):
        # The max rate for a single UE per PRB configuration in TM1 with MCS 28 QAM64
        max_phy_rate_tm1_dl = { 6 : 3.5e6,
                               15 : 11e6,
                               25 : 18e6,
                               50 : 36e6,
                               75 : 55e6,
                               100 : 75e6 }
        max_phy_rate_tm1_ul = { 6 : 1.7e6,
                               15 : 4.7e6,
                               25 : 10e6,
                               50 : 23e6,
                               75 : 34e6,
                               100 : 51e6 }
        if downlink:
            max_rate = max_phy_rate_tm1_dl[self.num_prb()]
        else:
            max_rate = max_phy_rate_tm1_ul[self.num_prb()]

        # MIMO only supported for Downlink
        if downlink:
            if self._txmode > 2:
                max_rate *= 2

            # For 6 PRBs the max throughput is significantly lower
            if self._txmode >= 2 and self.num_prb() == 6:
                max_rate *= 0.85

        # Assume we schedule all carriers
        max_rate *= num_carriers

        # Reduce expected UL rate due to missing extendedBSR support (see issue #1708)
        if downlink == False and num_carriers == 4 and self.num_prb() == 100:
            # all carriers run at 70% approx.
            max_rate *= 0.7

        return max_rate

# vim: expandtab tabstop=4 shiftwidth=4
