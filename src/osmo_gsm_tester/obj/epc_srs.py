# osmo_gsm_tester: specifics for running an SRS EPC process
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
from . import epc

def on_register_schemas():
    config_schema = {
        'enable_pcap': schema.BOOL_STR,
        'log_all_level': schema.STR,
        }
    schema.register_config_schema('epc', config_schema)

class srsEPC(epc.EPC):

    REMOTE_DIR = '/osmo-gsm-tester-srsepc'
    BINFILE = 'srsepc'
    CFGFILE = 'srsepc.conf'
    DBFILE = 'srsepc_user_db.csv'
    PCAPFILE = 'srsepc.pcap'
    LOGFILE = 'srsepc.log'

    def __init__(self, testenv, run_node):
        super().__init__(testenv, run_node, 'srsepc')
        self.run_dir = None
        self.config_file = None
        self.db_file = None
        self.log_file = None
        self.pcap_file = None
        self.process = None
        self.rem_host = None
        self.remote_inst = None
        self.remote_config_file = None
        self.remote_db_file = None
        self.remote_log_file = None
        self.remote_pcap_file = None
        self.enable_pcap = False
        self.subscriber_list = []

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
        if self.enable_pcap:
            try:
                self.rem_host.scpfrom('scp-back-pcap', self.remote_pcap_file, self.pcap_file)
            except Exception as e:
                self.log(repr(e))

    def start(self):
        self.log('Starting srsepc')
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()
        if self._run_node.is_local():
            self.start_locally()
        else:
            self.start_remotely()

    def start_remotely(self):
        remote_lib = self.remote_inst.child('lib')
        remote_binary = self.remote_inst.child('bin', srsEPC.BINFILE)

        # setting capabilities will later disable use of LD_LIBRARY_PATH from ELF loader -> modify RPATH instead.
        self.log('Setting RPATH for srsepc')
        self.rem_host.change_elf_rpath(remote_binary, remote_lib)
        # srsepc requires CAP_NET_ADMIN to create tunnel devices: ioctl(TUNSETIFF):
        self.log('Applying CAP_NET_ADMIN capability to srsepc')
        self.rem_host.setcap_net_admin(remote_binary)

        args = (remote_binary, self.remote_config_file)

        self.process = self.rem_host.RemoteProcess(srsEPC.BINFILE, args)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def start_locally(self):
        binary = inst.child('bin', BINFILE)
        lib = inst.child('lib')
        env = {}

        # setting capabilities will later disable use of LD_LIBRARY_PATH from ELF loader -> modify RPATH instead.
        self.log('Setting RPATH for srsepc')
        # srsepc binary needs patchelf <= 0.9 (0.10 and current master fail) to avoid failing during patch. OS#4389, patchelf-GH#192.
        util.change_elf_rpath(binary, util.prepend_library_path(lib), self.run_dir.new_dir('patchelf'))
        # srsepc requires CAP_NET_ADMIN to create tunnel devices: ioctl(TUNSETIFF):
        self.log('Applying CAP_NET_ADMIN capability to srsepc')
        util.setcap_net_admin(binary, self.run_dir.new_dir('setcap_net_admin'))

        args = (binary, os.path.abspath(self.config_file))

        self.process = process.Process(self.name(), self.run_dir, args, env=env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def configure(self):
        self.inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('srslte', self._run_node.run_label())))
        if not os.path.isdir(self.inst.child('lib')):
            raise log.Error('No lib/ in', self.inst)
        if not self.inst.isfile('bin', srsEPC.BINFILE):
            raise log.Error('No %s binary in' % srsEPC.BINFILE, self.inst)

        self.config_file = self.run_dir.child(srsEPC.CFGFILE)
        self.db_file = self.run_dir.child(srsEPC.DBFILE)
        self.log_file = self.run_dir.child(srsEPC.LOGFILE)
        self.pcap_file = self.run_dir.child(srsEPC.PCAPFILE)

        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            remote_prefix_dir = util.Dir(srsEPC.REMOTE_DIR)
            self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
            remote_run_dir = util.Dir(remote_prefix_dir.child(srsEPC.BINFILE))

            self.remote_config_file = remote_run_dir.child(srsEPC.CFGFILE)
            self.remote_db_file = remote_run_dir.child(srsEPC.DBFILE)
            self.remote_log_file = remote_run_dir.child(srsEPC.LOGFILE)
            self.remote_pcap_file = remote_run_dir.child(srsEPC.PCAPFILE)

        values = super().configure(['srsepc'])

        dbfile = self.db_file if self._run_node.is_local() else self.remote_db_file
        logfile = self.log_file if self._run_node.is_local() else self.remote_log_file
        pcapfile = self.pcap_file if self._run_node.is_local() else self.remote_pcap_file
        config.overlay(values, dict(epc=dict(db_filename=dbfile,
                                             log_filename=logfile,
                                             pcap_filename=pcapfile)))

        # Convert parsed boolean string to Python boolean:
        self.enable_pcap = util.str2bool(values['epc'].get('enable_pcap', 'false'))
        config.overlay(values, dict(epc={'enable_pcap': self.enable_pcap}))

        # Set qci for each subscriber:
        qci = values['epc'].get('qci', None)
        assert qci is not None
        for i in range(len(self.subscriber_list)):
            self.subscriber_list[i]['qci'] = qci
        config.overlay(values, dict(epc=dict(hss=dict(subscribers=self.subscriber_list))))

        self.dbg('SRSEPC CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(srsEPC.CFGFILE, values)
            self.dbg(r)
            f.write(r)
        with open(self.db_file, 'w') as f:
            r = template.render(srsEPC.DBFILE, values)
            self.dbg(r)
            f.write(r)

        if not self._run_node.is_local():
            self.rem_host.recreate_remote_dir(self.remote_inst)
            self.rem_host.scp('scp-inst-to-remote', str(self.inst), remote_prefix_dir)
            self.rem_host.recreate_remote_dir(remote_run_dir)
            self.rem_host.scp('scp-cfg-to-remote', self.config_file, self.remote_config_file)
            self.rem_host.scp('scp-db-to-remote', self.db_file, self.remote_db_file)

    def subscriber_add(self, modem, msisdn=None, algo_str=None):
        if msisdn is None:
            msisdn = self.testenv.msisdn()
        modem.set_msisdn(msisdn)

        if algo_str is None:
            algo_str = modem.auth_algo() or util.OSMO_AUTH_ALGO_NONE

        if algo_str != util.OSMO_AUTH_ALGO_NONE and not modem.ki():
            raise log.Error("Auth algo %r selected but no KI specified" % algo_str)

        if algo_str == 'milenage':
            if not modem.opc():
                raise log.Error("Auth algo milenage selected but no OPC specified")
            # srsepc's used_db uses token 'mil' for milenage:
            algo_str = 'mil'

        opc = (modem.opc() or '')
        subscriber_id = len(self.subscriber_list) # list index
        self.subscriber_list.append({'id': subscriber_id, 'imsi': modem.imsi(), 'msisdn': msisdn, 'auth_algo': algo_str, 'ki': modem.ki(), 'opc': opc, 'apn_ipaddr': modem.apn_ipaddr()})

        self.log('Add subscriber', msisdn=msisdn, imsi=modem.imsi(), subscriber_id=subscriber_id,
                 algo_str=algo_str)
        return subscriber_id

    def enb_is_connected(self, enb):
        # Match against sample line: "S1 Setup Request - eNB Name: srsenb01, eNB id: 0x19"
        stdout_lines = (self.process.get_stdout() or '').splitlines()
        for l in stdout_lines:
            if l.startswith('S1 Setup Request') and l.endswith('eNB id: %s' % hex(enb.id()).lower()):
                return True
        return False

    def running(self):
        return not self.process.terminated()

    def tun_addr(self):
        return '172.16.0.1'

# vim: expandtab tabstop=4 shiftwidth=4
