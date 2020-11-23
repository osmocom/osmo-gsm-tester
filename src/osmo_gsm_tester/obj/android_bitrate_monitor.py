# osmo_gsm_tester: specifics for monitoring the bit rate of an AndroidUE modem
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

from ..core import log
from .android_host import AndroidHost


class BitRateMonitor(AndroidHost):

##############
# PROTECTED
##############
    def __init__(self, testenv, run_dir, run_node, rem_host, data_interface):
        super().__init__('brate_monitor_%s' % run_node.run_addr())
        self.testenv = testenv
        self.rem_host = rem_host
        self._run_node = run_node
        self.run_dir = run_dir
        self.data_interface = data_interface
        self.rx_monitor_proc = None
        self.tx_monitor_proc = None

########################
# PUBLIC - INTERNAL API
########################
    def start(self):
        # start bit rate monitoring on Android UE
        popen_args_rx_mon = ['while true; do cat /sys/class/net/' + self.data_interface + '/statistics/rx_bytes;',
                             'sleep 1;', 'done']
        popen_args_tx_mon = ['while true; do cat /sys/class/net/' + self.data_interface + '/statistics/tx_bytes;',
                             'sleep 1;', 'done']
        self.rx_monitor_proc = self.run_androidue_cmd('start-rx-monitor', popen_args_rx_mon)
        self.testenv.remember_to_stop(self.rx_monitor_proc)
        self.rx_monitor_proc.launch()
        self.tx_monitor_proc = self.run_androidue_cmd('start-tx-monitor', popen_args_tx_mon)
        self.testenv.remember_to_stop(self.tx_monitor_proc)
        self.tx_monitor_proc.launch()

    def stop(self):
        self.testenv.stop_process(self.rx_monitor_proc)
        self.testenv.stop_process(self.tx_monitor_proc)

    def save_metrics(self, metrics_file):
        brate_rx_raw = self.rx_monitor_proc.get_stdout().split('\n')
        brate_tx_raw = self.tx_monitor_proc.get_stdout().split('\n')
        brate_rx_raw.remove('')
        brate_tx_raw.remove('')
        brate_rx_l = brate_rx_raw[1:]
        brate_tx_l = brate_tx_raw[1:]

        if len(brate_rx_l) < 2 or len(brate_tx_l) < 2:
            raise log.Error('Insufficient data available to write metrics file')

        # cut of elements if lists don't have the same length
        if len(brate_rx_l) > len(brate_tx_l):
            brate_rx_l = brate_rx_l[:len(brate_tx_l) - len(brate_rx_l)]
        if len(brate_rx_l) < len(brate_tx_l):
            brate_tx_l = brate_tx_l[:len(brate_rx_l) - len(brate_tx_l)]

        # get start value
        brate_rx_last = int(brate_rx_l[0])
        brate_tx_last = int(brate_tx_l[0])

        with open(metrics_file, 'w') as ue_metrics_fh:
            ue_metrics_fh.write('time;cc;earfcn;pci;rsrp;pl;cfo;pci_neigh;rsrp_neigh;cfo_neigh;'
                                + 'dl_mcs;dl_snr;dl_turbo;dl_brate;dl_bler;'
                                + 'ul_ta;ul_mcs;ul_buff;ul_brate;ul_bler;rf_o;rf_u;rf_l;'
                                + 'is_attached\n')
            for i in range(1, len(brate_rx_l)):
                time = '0'
                cc = '0'
                earfcn = '0'
                pci = '0'
                rsrp = '0'
                pl = '0'
                cfo = '0'
                pci_neigh = '0'
                rsrp_neigh = '0'
                cfo_neigh = '0'
                dl_mcs = '0'
                dl_snr = '0'
                dl_turbo = '0'
                dl_brate = str((int(brate_rx_l[i]) - brate_rx_last) * 8)
                brate_rx_last = int(brate_rx_l[i])
                dl_bler = '0'
                ul_ta = '0'
                ul_mcs = '0'
                ul_buff = '0'
                ul_brate = str((int(brate_tx_l[i]) - brate_tx_last) * 8)
                brate_tx_last = int(brate_tx_l[i])
                ul_bler = '0'
                rf_o = '0'
                rf_u = '0'
                rf_l = '0'
                is_attached = '0'

                line = time + ';' + cc + ';' + earfcn + ';' + pci + ';' + rsrp + ';' + pl + ';' + cfo + ';' \
                       + pci_neigh + ';' + rsrp_neigh + ';' + cfo_neigh + ';' + dl_mcs + ';' + dl_snr + ';' \
                       + dl_turbo + ';' + dl_brate + ';' + dl_bler + ';' + ul_ta + ';' + ul_mcs + ';' + ul_buff + ';' \
                       + ul_brate + ';' + ul_bler + ';' + rf_o + ';' + rf_u + ';' + rf_l + ';' + is_attached
                ue_metrics_fh.write(line + '\n')
