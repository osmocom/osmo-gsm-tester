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
from ..core import schema
from . import enb
from . import rfemu

def on_register_schemas():
    config_schema = {
        'license_server_addr': schema.IPV4,
        }
    schema.register_config_schema('amarisoft', config_schema)

    config_schema = {
        'log_options': schema.STR,
        }
    schema.register_config_schema('amarisoftenb', config_schema)

def rf_type_valid(rf_type_str):
    return rf_type_str in ('uhd', 'zmq', 'sdr')

class AmarisoftENB(enb.eNodeB):

    REMOTE_DIR = '/osmo-gsm-tester-amarisoftenb'
    BINFILE = 'lteenb'
    CFGFILE = 'amarisoft_enb.cfg'
    CFGFILE_SIB1 = 'amarisoft_sib1.asn'
    CFGFILE_SIB23 = 'amarisoft_sib23.asn'
    CFGFILE_RF = 'amarisoft_rf_driver.cfg'
    CFGFILE_DRB = 'amarisoft_drb.cfg'
    LOGFILE = 'lteenb.log'
    PHY_SIGNAL_FILE = 'lteenb.log.bin'

    def __init__(self, testenv, conf):
        super().__init__(testenv, conf, 'amarisoftenb')
        self.ue = None
        self.run_dir = None
        self.inst = None
        self._bin_prefix = None
        self.gen_conf = None
        self.config_file = None
        self.config_sib1_file = None
        self.config_sib23_file = None
        self.config_rf_file = None
        self.config_drb_file = None
        self.log_file = None
        self.process = None
        self.rem_host = None
        self.remote_inst = None
        self.remote_config_file =  None
        self.remote_config_sib1_file = None
        self.remote_config_sib23_file = None
        self.remote_config_rf_file = None
        self.remote_config_drb_file = None
        self.remote_log_file = None
        self.enable_measurements = False
        self.testenv = testenv
        if not rf_type_valid(conf.get('rf_dev_type', None)):
            raise log.Error('Invalid rf_dev_type=%s' % conf.get('rf_dev_type', None))

    def bin_prefix(self):
        if self._bin_prefix is None:
            self._bin_prefix = os.getenv('AMARISOFT_PATH_ENB', None)
            if self._bin_prefix == None:
                self._bin_prefix  = self.testenv.suite().trial().get_inst('amarisoftenb', self._run_node.run_label())
        return self._bin_prefix

    def cleanup(self):
        if self.process is None:
            return
        if self._run_node.is_local():
            return
        # copy back files (may not exist, for instance if there was an early error of process):
        try:
            self.rem_host.scpfrom('scp-back-log', self.remote_log_file, self.log_file)
        except Exception as e:
            self.log(repr(e))

        try:
            self.rem_host.scpfrom('scp-back-phy-signal-log', self.remote_phy_signal_file, self.phy_signal_file)
        except Exception as e:
            self.log(repr(e))
        # Clean up for parent class:
        super().cleanup()

    def start(self, epc):
        self.log('Starting AmarisoftENB')
        self._epc = epc
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()
        self._start()

        # send t+Enter to enable console trace
        self.dbg('Enabling console trace')
        self.process.stdin_write('t\n')

    def _start(self):
        if self._run_node.is_local():
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

        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def stop(self):
        # Not implemented
        pass

    def gen_conf_file(self, path, filename, values):
        self.dbg('AmarisoftENB ' + filename + ':\n' + pprint.pformat(values))
        with open(path, 'w') as f:
            r = template.render(filename, values)
            self.dbg(r)
            f.write(r)

    def configure(self):
        self.inst = util.Dir(os.path.abspath(self.bin_prefix()))
        if not self.inst.isfile('', AmarisoftENB.BINFILE):
            raise log.Error('No %s binary in' % AmarisoftENB.BINFILE, self.inst)

        self.config_file = self.run_dir.child(AmarisoftENB.CFGFILE)
        self.config_sib1_file = self.run_dir.child(AmarisoftENB.CFGFILE_SIB1)
        self.config_sib23_file = self.run_dir.child(AmarisoftENB.CFGFILE_SIB23)
        self.config_rf_file = self.run_dir.child(AmarisoftENB.CFGFILE_RF)
        self.config_drb_file = self.run_dir.child(AmarisoftENB.CFGFILE_DRB)
        self.log_file = self.run_dir.child(AmarisoftENB.LOGFILE)
        self.phy_signal_file = self.run_dir.child(AmarisoftENB.PHY_SIGNAL_FILE)

        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            remote_prefix_dir = util.Dir(AmarisoftENB.REMOTE_DIR)
            self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
            remote_run_dir = util.Dir(remote_prefix_dir.child(AmarisoftENB.BINFILE))

            self.remote_config_file = remote_run_dir.child(AmarisoftENB.CFGFILE)
            self.remote_config_sib1_file = remote_run_dir.child(AmarisoftENB.CFGFILE_SIB1)
            self.remote_config_sib23_file = remote_run_dir.child(AmarisoftENB.CFGFILE_SIB23)
            self.remote_config_rf_file = remote_run_dir.child(AmarisoftENB.CFGFILE_RF)
            self.remote_config_drb_file = remote_run_dir.child(AmarisoftENB.CFGFILE_DRB)
            self.remote_log_file = remote_run_dir.child(AmarisoftENB.LOGFILE)
            self.remote_phy_signal_file = remote_run_dir.child(AmarisoftENB.PHY_SIGNAL_FILE)

        values = super().configure(['amarisoft', 'amarisoftenb'])

        # Convert parsed boolean string to Python boolean:
        self.enable_measurements = util.str2bool(values['enb'].get('enable_measurements', 'false'))
        config.overlay(values, dict(enb={'enable_measurements': self.enable_measurements}))

        config.overlay(values, dict(enb={'enable_dl_awgn': util.str2bool(values['enb'].get('enable_dl_awgn', 'false'))}))

        # Remove EEA0 from cipher list, if specified, as it's always assumed as default
        cipher_list = values['enb'].get('cipher_list', None)
        if "eea0" in cipher_list: cipher_list.remove("eea0")

        # We need to set some specific variables programatically here to match IP addresses:
        if self._conf.get('rf_dev_type') == 'zmq':
            base_srate = self.num_prb2base_srate(self.num_prb())
            rf_dev_args = self.get_zmq_rf_dev_args(values)
            config.overlay(values, dict(enb=dict(sample_rate = base_srate / (1000*1000),
                                                 rf_dev_args = rf_dev_args)))

        # Set UHD frame size as a function of the cell bandwidth on B2XX
        if self._conf.get('rf_dev_type') == 'uhd' and values['enb'].get('rf_dev_args', None) is not None:
            if 'b200' in values['enb'].get('rf_dev_args'):
                rf_dev_args = values['enb'].get('rf_dev_args', '')
                rf_dev_args += ',' if rf_dev_args != '' and not rf_dev_args.endswith(',') else ''

                if self._txmode == 1:
                    # SISO config
                    if self._num_prb < 25:
                        rf_dev_args += 'send_frame_size=512,recv_frame_size=512'
                    elif self._num_prb == 25:
                        rf_dev_args += 'send_frame_size=1024,recv_frame_size=1024'
                    else:
                        rf_dev_args += ''
                else:
                    # MIMO config
                    if self._num_prb == 6:
                        rf_dev_args += 'send_frame_size=512,recv_frame_size=512'
                    else:
                        rf_dev_args += 'num_recv_frames=64,num_send_frames=64'

                    if self._num_prb > 50:
                        # Reduce over the wire format to sc12
                        rf_dev_args += ',otw_format=sc12'

                config.overlay(values, dict(enb=dict(rf_dev_args=rf_dev_args)))

        logfile = self.log_file if self._run_node.is_local() else self.remote_log_file
        config.overlay(values, dict(enb=dict(log_filename=logfile)))

        phy_signal_file = self.phy_signal_file if self._run_node.is_local() else self.remote_phy_signal_file
        config.overlay(values, dict(enb=dict(phy_signal_file=phy_signal_file)))

        # rf driver is shared between amarisoft enb and ue, so it has a
        # different cfg namespace 'trx'. Copy needed values over there:
        config.overlay(values, dict(trx=dict(rf_dev_type=values['enb'].get('rf_dev_type', None),
                                             rf_dev_args=values['enb'].get('rf_dev_args', None),
                                             rf_dev_sync=values['enb'].get('rf_dev_sync', None),
                                             rx_gain=values['enb'].get('rx_gain', None),
                                             tx_gain=values['enb'].get('tx_gain', None),
                                             rx_ant=values['enb'].get('rx_ant', None),
                                            )))

        self.gen_conf = values

        self.gen_conf_file(self.config_file, AmarisoftENB.CFGFILE, values)
        self.gen_conf_file(self.config_sib1_file, AmarisoftENB.CFGFILE_SIB1, values)
        self.gen_conf_file(self.config_sib23_file, AmarisoftENB.CFGFILE_SIB23, values)
        self.gen_conf_file(self.config_rf_file, AmarisoftENB.CFGFILE_RF, values)
        self.gen_conf_file(self.config_drb_file, AmarisoftENB.CFGFILE_DRB, values)

        if not self._run_node.is_local():
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

    def get_counter(self, counter_name):
        if counter_name == 'prach_received':
            return self.process.get_counter_stdout('PRACH:')
        raise log.Error('counter %s not implemented!' % counter_name)

    def get_kpis(self):
        return {}

    def get_rfemu(self, cell=0, dl=True):
        cell_list = self.gen_conf['enb'].get('cell_list', None)
        if cell_list is None or len(cell_list) < cell + 1:
            raise log.Error('cell_list attribute or subitem not found!')
        rfemu_cfg = cell_list[cell].get('dl_rfemu', None)
        if rfemu_cfg is None: # craft amarisoft by default:
            rfemu_cfg = {'type': 'amarisoftctl',
                         'addr': self.addr(),
                         'ports': [9001]
                         }
        if rfemu_cfg['type'] == 'amarisoftctl': # this one requires extra config:
            config.overlay(rfemu_cfg, dict(cell_id=cell_list[cell]['cell_id']))
        rfemu_obj = rfemu.get_instance_by_type(rfemu_cfg['type'], rfemu_cfg)
        return rfemu_obj

    def ue_max_rate(self, downlink=True, num_carriers=1):
        if self._duplex == 'fdd':
            return self.ue_max_rate_fdd(downlink, num_carriers)
        else:
            return self.ue_max_rate_tdd(downlink, num_carriers)

    def ue_max_rate_fdd(self, downlink, num_carriers):
        # The max rate for a single UE per PRB configuration in TM1 with MCS 28 QAM64
        max_phy_rate_tm1_dl = { 6 : 3.2e6,
                               15 : 9.2e6,
                               25 : 18e6,
                               50 : 36e6,
                               75 : 55e6,
                               100 : 75e6 }
        max_phy_rate_tm1_ul = { 6 : 2.0e6,
                               15 : 5.1e6,
                               25 : 10e6,
                               50 : 21e6,
                               75 : 32e6,
                               100 : 47e6 }
        if downlink:
            max_rate = max_phy_rate_tm1_dl[self.num_prb()]
        else:
            max_rate = max_phy_rate_tm1_ul[self.num_prb()]

        # MIMO only supported for Downlink
        if downlink:
            if self._txmode > 2:
                max_rate *= 2
            # Lower max MCS for TM2 and above results in lower max rate
            if self._txmode >= 2 and self.num_prb() <= 25:
                max_rate *= 0.85

        # Assume we schedule all carriers
        max_rate *= num_carriers

        # Reduce expected UL rate due to bug in UCI scheduling in Amarisoft eNB
        if downlink == False and num_carriers == 2:
            # 2nd carrier @ 25%
            max_rate = max_rate / 2 + (.25 * max_rate / 2)

        return max_rate

    def ue_max_rate_tdd(self, downlink, num_carriers):
        # Max rate calculation for TDD depends on the acutal TDD configuration
        # See: https://www.sharetechnote.com/html/Handbook_LTE_ThroughputCalculationExample_TDD.html
        # and https://i0.wp.com/www.techtrained.com/wp-content/uploads/2017/09/Blog_Post_1_TDD_Max_Throughput_Theoretical.jpg
        max_phy_rate_tdd_uldl_config0_sp0 = { 6 : 1.5e6,
                               15 : 3.7e6,
                               25 : 6.1e6,
                               50 : 12.2e6,
                               75 : 18.4e6,
                               100 : 54.5e6 }
        if downlink:
            max_rate = max_phy_rate_tdd_uldl_config0_sp0[self.num_prb()]
        else:
            return 1e6 # dummy value, we need to replace that later

# vim: expandtab tabstop=4 shiftwidth=4
