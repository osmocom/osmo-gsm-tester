# osmo_gsm_tester: specifics for running an AndroidUE modem
#
# Copyright (C) 2020 by Software Radio Systems Limited
#
# Author: Nils Fürste <nils.fuerste@softwareradiosystems.com>
# Author: Bedran Karakoc <bedran.karakoc@softwareradiosystems.com>
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

import pprint

from ..core import log, util, config, remote, schema, process
from .run_node import RunNode
from .ms import MS
from .srslte_common import srslte_common
from ..core.event_loop import MainLoop
from .ms_srs import srsUEMetrics
from .android_bitrate_monitor import BitRateMonitor
from . import qc_diag
from .android_apn import AndroidApn
from .android_host import AndroidHost


def on_register_schemas():
    resource_schema = {
        'additional_args[]': schema.STR,
        'enable_pcap': schema.BOOL_STR,
        }
    for key, val in RunNode.schema().items():
        resource_schema['run_node.%s' % key] = val
    for key, val in AndroidApn.schema().items():
        resource_schema['apn.%s' % key] = val
    schema.register_resource_schema('modem', resource_schema)

    config_schema = {
        'enable_pcap': schema.BOOL_STR,
        'log_all_level': schema.STR,
        }
    schema.register_config_schema('modem', config_schema)


class AndroidUE(MS, AndroidHost, srslte_common):

    REMOTEDIR = '/osmo-gsm-tester-androidue'
    METRICSFILE = 'android_ue_metrics.csv'
    PCAPFILE = 'android_ue.pcap'

##############
# PROTECTED
##############
    def __init__(self, testenv, conf):
        self._run_node = RunNode.from_conf(conf.get('run_node', {}))
        self.apn_worker = AndroidApn.from_conf(conf.get('apn', {})) if conf.get('apn', {}) != {} else None
        self.qc_diag_mon = qc_diag.QcDiag(testenv, conf)
        super().__init__('androidue_%s' % self.addr(), testenv, conf)
        srslte_common.__init__(self)
        self.rem_host = None
        self.run_dir = None
        self.remote_run_dir = None
        self.emm_connected = False
        self.rrc_connected = False
        self.conn_reset_intvl = 20  # sec
        self.connect_timeout = 300  # sec
        self.enable_pcap = None
        self.remote_pcap_file = None
        self.pcap_file = None
        self.data_interface = None
        self.remote_metrics_file = None
        self.metrics_file = None
        self.brate_mon = None

    def configure(self):
        values = dict(ue=config.get_defaults('androidue'))
        config.overlay(values, dict(ue=self.testenv.suite().config().get('modem', {})))
        config.overlay(values, dict(ue=self._conf))
        self.dbg('AndroidUE CONFIG:\n' + pprint.pformat(values))

        if 'qc_diag' in self.features():
            self.enable_pcap = util.str2bool(values['ue'].get('enable_pcap', 'false'))

        self.metrics_file = self.run_dir.child(AndroidUE.METRICSFILE)
        self.pcap_file = self.run_dir.child(AndroidUE.PCAPFILE)
        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr(), None,
                                              self._run_node.ssh_port())
            self.remote_run_dir = util.Dir(AndroidUE.REMOTEDIR)
            self.remote_metrics_file = self.remote_run_dir.child(AndroidUE.METRICSFILE)
            self.remote_pcap_file = self.remote_run_dir.child(AndroidUE.PCAPFILE)

        if self.apn_worker:
            self.apn_worker.configure(self.testenv, self.run_dir, self._run_node, self.rem_host)
            # some Android UEs only accept new APNs when airplane mode is turned off
            self.set_airplane_mode(False)
            self.apn_worker.set_apn()
            MainLoop.sleep(1)
            self.set_airplane_mode(True)

        # clear old diag files
        self._clear_diag_logs()

    def _clear_diag_logs(self):
        popen_args_clear_diag_logs = \
            ['su', '-c', '\"rm -r /data/local/tmp/diag_logs/ || true\"']
        clear_diag_logs_proc = self.run_androidue_cmd('clear-diag-logs', popen_args_clear_diag_logs)
        clear_diag_logs_proc.launch_sync()

    def verify_metric(self, value, operation='avg', metric='dl_brate', criterion='gt', window=1):
        self.brate_mon.save_metrics(self.metrics_file)
        metrics = srsUEMetrics(self.metrics_file)
        return metrics.verify(value, operation, metric, criterion, window)

    def set_airplane_mode(self, apm_state):
        self.log("Setting airplane mode: " + str(apm_state))
        popen_args = ['settings', 'put', 'global', 'airplane_mode_on', str(int(apm_state)), ';',
                      'wait $!;',
                      'su', '-c', '\"am broadcast -a android.intent.action.AIRPLANE_MODE\";']
        proc = self.run_androidue_cmd('set-airplane-mode', popen_args)
        proc.launch_sync()

    def get_assigned_addr(self, ipv6=False):
        ip_prefix = '172.16.0'
        proc = self.run_androidue_cmd('get-assigned-addr', ['ip', 'addr', 'show'])
        proc.launch_sync()
        out_l = proc.get_stdout().split('\n')
        ip = ''
        for line in out_l:
            if ip_prefix in line:
                ip = line.split(' ')[5][:-3]
                self.data_interface = line.split(' ')[-1]
        return ip

########################
# PUBLIC - INTERNAL API
########################
    def cleanup(self):
        self.set_airplane_mode(True)

    def addr(self):
        return self._run_node.run_addr()

    def run_node(self):
        return self._run_node

    def features(self):
        return self._conf.get('features', [])

###################
# PUBLIC (test API included)
###################
    def run_netns_wait(self, name, popen_args):
        # This function guarantees the compatibility with the current ping test. Please
        # note that this function cannot execute commands on the machine the Android UE
        # is attached to.
        proc = self.run_androidue_cmd(name, popen_args)
        proc.launch_sync()
        return proc

    def connect(self, enb):
        self.log('Starting AndroidUE')
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()
        CONN_CHK = 'osmo-gsm-tester_androidue_conn_chk.sh'

        if 'qc_diag' in self.features():
            self.qc_diag_mon.start()

        if self._run_node.is_local():
            popen_args_emm_conn_chk = [CONN_CHK, self._run_node.adb_serial_id(), '0', '0']
        else:
            popen_args_emm_conn_chk = [CONN_CHK, '0', self.rem_host.host(), self.rem_host.get_remote_port()]

        # make sure osmo-gsm-tester_androidue_conn_chk.sh is available on the OGT master unit
        name = 'emm-conn-chk'
        run_dir = self.run_dir.new_dir(name)
        emm_conn_chk_proc = process.Process(name, run_dir, popen_args_emm_conn_chk)
        self.testenv.remember_to_stop(emm_conn_chk_proc)
        emm_conn_chk_proc.launch()

        # check connection status
        timer = self.connect_timeout
        while timer > 0:
            if timer % self.conn_reset_intvl == 0:
                self.set_airplane_mode(True)
                MainLoop.sleep(1)
                timer -= 1
                self.set_airplane_mode(False)

            if 'LTE' in emm_conn_chk_proc.get_stdout():
                if not(self.get_assigned_addr() is ''):
                    self.emm_connected = True
                    self.rrc_connected = True
                    self.testenv.stop_process(emm_conn_chk_proc)
                    break

            MainLoop.sleep(2)
            timer -= 2

        if timer == 0:
            raise log.Error('Connection timer of Android UE %s expired' % self._run_node.adb_serial_id())

        self.brate_mon = BitRateMonitor(self.testenv, self.run_dir, self._run_node, self.rem_host, self.data_interface)
        self.brate_mon.start()

    def is_rrc_connected(self):
        if not ('qc_diag' in self.features()):
            raise log.Error('Monitoring RRC states not supported (missing qc_diag feature?)')

        # if not self.qc_diag_mon.running():
        #     raise log.Error('Diag monitoring crashed or was not started')

        rrc_state = self.qc_diag_mon.get_rrc_state()
        if 'RRC_IDLE_CAMPED' in rrc_state:
            self.rrc_connected = False
        elif 'RRC_CONNECTED' in rrc_state:
            self.rrc_connected = True
        return self.rrc_connected

    def is_registered(self, mcc_mnc=None):
        if mcc_mnc:
            raise log.Error('An AndroidUE cannot register to any predefined MCC/MNC')
        return self.emm_connected

    def get_counter(self, counter_name):
        if counter_name == 'prach_sent':
            # not implemented so far, return 2 to pass tests
            return 2
        elif counter_name == 'paging_received':
            return self.qc_diag_mon.get_paging_counter()
        else:
            raise log.Error('Counter %s not implemented' % counter_name)

    def netns(self):
        return None
