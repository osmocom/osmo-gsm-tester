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
    return rf_type_str in ('zmq', 'uhd', 'soapy', 'bladerf')

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

class srsENB(enb.eNodeB):

    REMOTE_DIR = '/osmo-gsm-tester-srsenb'
    BINFILE = 'srsenb'
    CFGFILE = 'srsenb.conf'
    CFGFILE_SIB = 'srsenb_sib.conf'
    CFGFILE_RR = 'srsenb_rr.conf'
    CFGFILE_DRB = 'srsenb_drb.conf'
    LOGFILE = 'srsenb.log'
    PCAPFILE = 'srsenb.pcap'

    def __init__(self, suite_run, conf):
        super().__init__(suite_run, conf, srsENB.BINFILE)
        self.ue = None
        self.run_dir = None
        self.config_file = None
        self.config_sib_file = None
        self.config_rr_file = None
        self.config_drb_file = None
        self.log_file = None
        self.pcap_file = None
        self.process = None
        self.rem_host = None
        self.remote_config_file =  None
        self.remote_config_sib_file = None
        self.remote_config_rr_file = None
        self.remote_config_drb_file = None
        self.remote_log_file = None
        self.remote_pcap_file = None
        self.enable_pcap = False
        self.suite_run = suite_run
        self.remote_user = conf.get('remote_user', None)
        if not rf_type_valid(conf.get('rf_dev_type', None)):
            raise log.Error('Invalid rf_dev_type=%s' % conf.get('rf_dev_type', None))

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
        if self.enable_pcap:
            try:
                self.rem_host.scpfrom('scp-back-pcap', self.remote_pcap_file, self.pcap_file)
            except Exception as e:
                self.log(repr(e))

    def setup_runs_locally(self):
        return self.remote_user is None

    def start(self, epc):
        self.log('Starting srsENB')
        self._epc = epc
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()
        if self.remote_user:
            self.start_remotely()
        else:
            self.start_locally()

        # send t+Enter to enable console trace
        self.dbg('Enabling console trace')
        self.process.stdin_write('t\n')

    def start_remotely(self):
        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('srslte')))
        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in', self.inst)
        if not self.inst.isfile('bin', srsENB.BINFILE):
            raise log.Error('No %s binary in' % srsENB.BINFILE, self.inst)

        self.rem_host = remote.RemoteHost(self.run_dir, self.remote_user, self._addr)
        remote_prefix_dir = util.Dir(srsENB.REMOTE_DIR)
        self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
        remote_run_dir = util.Dir(remote_prefix_dir.child(srsENB.BINFILE))

        self.remote_config_file = remote_run_dir.child(srsENB.CFGFILE)
        self.remote_config_sib_file = remote_run_dir.child(srsENB.CFGFILE_SIB)
        self.remote_config_rr_file = remote_run_dir.child(srsENB.CFGFILE_RR)
        self.remote_config_drb_file = remote_run_dir.child(srsENB.CFGFILE_DRB)
        self.remote_log_file = remote_run_dir.child(srsENB.LOGFILE)
        self.remote_pcap_file = remote_run_dir.child(srsENB.PCAPFILE)

        self.rem_host.recreate_remote_dir(self.remote_inst)
        self.rem_host.scp('scp-inst-to-remote', str(self.inst), remote_prefix_dir)
        self.rem_host.recreate_remote_dir(remote_run_dir)
        self.rem_host.scp('scp-cfg-to-remote', self.config_file, self.remote_config_file)
        self.rem_host.scp('scp-cfg-sib-to-remote', self.config_sib_file, self.remote_config_sib_file)
        self.rem_host.scp('scp-cfg-rr-to-remote', self.config_rr_file, self.remote_config_rr_file)
        self.rem_host.scp('scp-cfg-drb-to-remote', self.config_drb_file, self.remote_config_drb_file)

        remote_env = { 'LD_LIBRARY_PATH': self.remote_inst.child('lib') }
        remote_binary = self.remote_inst.child('bin', srsENB.BINFILE)
        args = (remote_binary, self.remote_config_file,
                '--enb_files.sib_config=' + self.remote_config_sib_file,
                '--enb_files.rr_config=' + self.remote_config_rr_file,
                '--enb_files.drb_config=' + self.remote_config_drb_file,
                '--log.filename=' + self.remote_log_file,
                '--pcap.filename=' + self.remote_pcap_file)

        self.process = self.rem_host.RemoteProcess(srsENB.BINFILE, args, remote_env=remote_env)
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def start_locally(self):
        inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('srslte')))

        binary = inst.child('bin', srsENB.BINFILE)
        if not os.path.isfile(binary):
            raise log.Error('Binary missing:', binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in', inst)

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        args = (binary, os.path.abspath(self.config_file),
                '--enb_files.sib_config=' + os.path.abspath(self.config_sib_file),
                '--enb_files.rr_config=' + os.path.abspath(self.config_rr_file),
                '--enb_files.drb_config=' + os.path.abspath(self.config_drb_file),
                '--log.filename=' + self.log_file,
                '--pcap.filename=' + self.pcap_file)

        self.process = process.Process(self.name(), self.run_dir, args, env=env)
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def gen_conf_file(self, path, filename, values):
        self.dbg('srsENB ' + filename + ':\n' + pprint.pformat(values))

        with open(path, 'w') as f:
            r = template.render(filename, values)
            self.dbg(r)
            f.write(r)

    def configure(self):
        values = super().configure(['srsenb'])

        # Convert parsed boolean string to Python boolean:
        self.enable_pcap = util.str2bool(values['enb'].get('enable_pcap', 'false'))
        config.overlay(values, dict(enb={'enable_pcap': self.enable_pcap}))

        self._num_cells = int(values['enb'].get('num_cells', None))
        assert self._num_cells

        # We need to set some specific variables programatically here to match IP addresses:
        if self._conf.get('rf_dev_type') == 'zmq':
            base_srate = num_prb2base_srate(self.num_prb())
            rf_dev_args = 'fail_on_disconnect=true' \
                        + ',tx_port=tcp://' + self.addr() + ':2000' \
                        + ',tx_port2=tcp://' + self.addr() + ':2002' \
                        + ',rx_port=tcp://' + self.ue.addr() + ':2001' \
                        + ',rx_port2=tcp://' + self.ue.addr() + ':2003' \
                        + ',tx_freq=2630e6,rx_freq=2510e6,tx_freq2=2650e6,rx_freq2=2530e6' \
                        + ',id=enb,base_srate=' + str(base_srate)
            config.overlay(values, dict(enb=dict(rf_dev_args=rf_dev_args)))

        # Set UHD frame size as a function of the cell bandwidth on B2XX
        if self._conf.get('rf_dev_type') == 'UHD' and values['enb'].get('rf_dev_args', None) is not None:
            if 'b200' in values['enb'].get('rf_dev_args'):
                rf_dev_args = values['enb'].get('rf_dev_args', '')
                rf_dev_args += ',' if rf_dev_args != '' and not rf_dev_args.endswith(',') else ''

                if self._num_prb < 25:
                    rf_dev_args += 'send_frame_size=512,recv_frame_size=512'
                elif self._num_prb == 25:
                    rf_dev_args += 'send_frame_size=1024,recv_frame_size=1024'
                elif self._num_prb > 25:
                    rf_dev_args += 'num_recv_frames=64,num_send_frames=64'

                if self._num_prb > 50:
                    # Reduce over the wire format to sc12
                    rf_dev_args += ',otw_format=sc12'

                config.overlay(values, dict(enb=dict(rf_dev_args=rf_dev_args)))

        self.config_file = self.run_dir.child(srsENB.CFGFILE)
        self.config_sib_file = self.run_dir.child(srsENB.CFGFILE_SIB)
        self.config_rr_file = self.run_dir.child(srsENB.CFGFILE_RR)
        self.config_drb_file = self.run_dir.child(srsENB.CFGFILE_DRB)
        self.log_file = self.run_dir.child(srsENB.LOGFILE)
        self.pcap_file = self.run_dir.child(srsENB.PCAPFILE)

        self.gen_conf_file(self.config_file, srsENB.CFGFILE, values)
        self.gen_conf_file(self.config_sib_file, srsENB.CFGFILE_SIB, values)
        self.gen_conf_file(self.config_rr_file, srsENB.CFGFILE_RR, values)
        self.gen_conf_file(self.config_drb_file, srsENB.CFGFILE_DRB, values)

    def ue_add(self, ue):
        if self.ue is not None:
            raise log.Error("More than one UE per ENB not yet supported (ZeroMQ)")
        self.ue = ue

    def running(self):
        return not self.process.terminated()

# vim: expandtab tabstop=4 shiftwidth=4
