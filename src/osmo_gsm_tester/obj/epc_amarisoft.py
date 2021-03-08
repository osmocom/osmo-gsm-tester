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
import time

from ..core import log, util, config, template, process, remote
from ..core import schema
from . import epc

def on_register_schemas():
    config_schema = {
        'license_server_addr': schema.IPV4,
        }
    schema.register_config_schema('amarisoft', config_schema)

class AmarisoftEPC(epc.EPC):

    REMOTE_DIR = '/osmo-gsm-tester-amarisoftepc'
    BINFILE = 'ltemme'
    CFGFILE = 'amarisoft_ltemme.cfg'
    LOGFILE = 'ltemme.log'
    IFUPFILE = 'mme-ifup'
    LTESIM_BINFILE = 'ltesim_server'

    def __init__(self, testenv, run_node):
        super().__init__(testenv, run_node, 'amarisoftepc')
        self.run_dir = None
        self.config_file = None
        self.log_file = None
        self.ifup_file = None
        self.process = None
        self.rem_host = None
        self.remote_run_dir = None
        self.remote_inst = None
        self.remote_config_file = None
        self.remote_log_file = None
        self.remote_ifup_file = None
        self._bin_prefix = None
        self.inst = None
        self.subscriber_list = []

    def bin_prefix(self):
        if self._bin_prefix is None:
            self._bin_prefix = os.getenv('AMARISOFT_PATH_EPC', None)
            if self._bin_prefix == None:
                self._bin_prefix  = self.testenv.suite().trial().get_inst('amarisoftepc', self._run_node.run_label())
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

    def start(self):
        self.log('Starting amarisoftepc')
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()
        if self._run_node.is_local():
            self.start_locally()
        else:
            self.start_remotely()
            self.start_ltesim_remotely()

    def start_remotely(self):
        remote_binary = self.remote_inst.child('', AmarisoftEPC.BINFILE)
        # setting capabilities will later disable use of LD_LIBRARY_PATH from ELF loader -> modify RPATH instead.
        self.log('Setting RPATH for amarisoftepc')
        self.rem_host.change_elf_rpath(remote_binary, str(self.remote_inst))
        # amarisoftepc requires CAP_NET_ADMIN to create tunnel devices: ioctl(TUNSETIFF):
        self.log('Applying CAP_NET_ADMIN capability to amarisoftepc')
        self.rem_host.setcap_net_admin(remote_binary)

        args = (remote_binary, self.remote_config_file)

        self.process = self.rem_host.RemoteProcessSafeExit(AmarisoftEPC.BINFILE, self.remote_run_dir, args)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def start_locally(self):
        binary = self.inst.child('', BINFILE)

        env = {}
        # setting capabilities will later disable use of LD_LIBRARY_PATH from ELF loader -> modify RPATH instead.
        self.log('Setting RPATH for amarisoftepc')
        util.change_elf_rpath(binary, util.prepend_library_path(str(self.inst)), self.run_dir.new_dir('patchelf'))
        # amarisoftepc requires CAP_NET_ADMIN to create tunnel devices: ioctl(TUNSETIFF):
        self.log('Applying CAP_NET_ADMIN capability to amarisoftepc')
        util.setcap_net_admin(binary, self.run_dir.new_dir('setcap_net_admin'))

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        args = (binary, os.path.abspath(self.config_file))

        self.process = process.Process(self.name(), self.run_dir, args, env=env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def start_ltesim_remotely(self):
        # Sleep for a moment to give MME time to start up create TUN device
        time.sleep(5)
        remote_binary = self.remote_inst.child('', AmarisoftEPC.LTESIM_BINFILE)
        args = (remote_binary, "-a " + self.tun_addr())
        self.log('Launching ltesim_server')
        self.ltesim_process = self.rem_host.RemoteProcess(AmarisoftEPC.LTESIM_BINFILE, args)
        self.testenv.remember_to_stop(self.ltesim_process)
        self.ltesim_process.launch()

    def configure(self):
        self.inst = util.Dir(os.path.abspath(self.bin_prefix()))
        if not self.inst.isfile('', AmarisoftEPC.BINFILE):
            raise log.Error('No %s binary in' % AmarisoftEPC.BINFILE, self.inst)

        self.config_file = self.run_dir.child(AmarisoftEPC.CFGFILE)
        self.log_file = self.run_dir.child(AmarisoftEPC.LOGFILE)
        self.ifup_file = self.run_dir.new_file(AmarisoftEPC.IFUPFILE)
        os.chmod(self.ifup_file, 0o744) # add execution permission
        self.dbg(config_file=self.config_file)
        with open(self.ifup_file, 'w') as f:
            r = '''#!/bin/sh
            set -x -e
            # script + sudoers file available in osmo-gsm-tester.git/utils/{bin,sudoers.d}
            sudo /usr/local/bin/osmo-gsm-tester_amarisoft_ltemme_ifup.sh "$@"
            '''
            f.write(r)

        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            remote_prefix_dir = util.Dir(AmarisoftEPC.REMOTE_DIR)
            self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
            self.remote_run_dir = util.Dir(remote_prefix_dir.child(AmarisoftEPC.BINFILE))

            self.remote_config_file = self.remote_run_dir.child(AmarisoftEPC.CFGFILE)
            self.remote_log_file = self.remote_run_dir.child(AmarisoftEPC.LOGFILE)
            self.remote_ifup_file = self.remote_run_dir.child(AmarisoftEPC.IFUPFILE)

        values = super().configure(['amarisoft', 'amarisoftepc'])

        logfile = self.log_file if self._run_node.is_local() else self.remote_log_file
        ifupfile = self.ifup_file if self._run_node.is_local() else self.remote_ifup_file
        config.overlay(values, dict(epc=dict(log_filename=logfile,
                                             ifup_filename=ifupfile)))

        # Retrieve and overlay UE count parameter to first subscriber
        sub_count = self.testenv.suite().config().get('modem', None)
        sub_count = sub_count['count'] if sub_count is not None and 'count' in sub_count else 1
        self.subscriber_list[0]['count'] = sub_count
        config.overlay(values, dict(epc=dict(hss=dict(subscribers=self.subscriber_list))))

        self.dbg('SRSEPC CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(AmarisoftEPC.CFGFILE, values)
            self.dbg(r)
            f.write(r)

        if not self._run_node.is_local():
            self.rem_host.recreate_remote_dir(self.remote_inst)
            self.rem_host.scp('scp-inst-to-remote', str(self.inst), remote_prefix_dir)
            self.rem_host.recreate_remote_dir(self.remote_run_dir)
            self.rem_host.scp('scp-cfg-to-remote', self.config_file, self.remote_config_file)
            self.rem_host.scp('scp-ifup-to-remote', self.ifup_file, self.remote_ifup_file)

    def subscriber_add(self, modem, msisdn=None, algo_str=None):
        if msisdn is None:
            msisdn = modem.msisdn()

        if algo_str is None:
            algo_str = modem.auth_algo() or util.OSMO_AUTH_ALGO_NONE

        if algo_str != util.OSMO_AUTH_ALGO_NONE and not modem.ki():
            raise log.Error("Auth algo %r selected but no KI specified" % algo_str)

        if algo_str == 'milenage' and not modem.opc():
            raise log.Error("Auth algo milenage selected but no OPC specified")

        subscriber_id = len(self.subscriber_list) # list index
        self.subscriber_list.append({'id': subscriber_id, 'imsi': modem.imsi(), 'msisdn': msisdn, 'auth_algo': algo_str, 'ki': modem.ki(), 'opc': modem.opc(), 'apn_ipaddr': modem.apn_ipaddr()})

        self.log('Add subscriber', msisdn=msisdn, imsi=modem.imsi(), subscriber_id=subscriber_id,
                 algo_str=algo_str)
        return subscriber_id

    def enb_is_connected(self, enb):
        # TODO: improve this a bit, like matching IP addr of enb. CTRL iface?
        # The string is only available in log file, not in stdout:
        #return 'S1 setup response' in (self.process.get_stdout() or '')
        return True

    def running(self):
        return not self.process.terminated()

    def tun_addr(self):
        # TODO: set proper addr
        return '192.168.4.1'

    def get_kpis(self):
        return {}

# vim: expandtab tabstop=4 shiftwidth=4
