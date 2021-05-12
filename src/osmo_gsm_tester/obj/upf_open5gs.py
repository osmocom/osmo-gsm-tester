# osmo_gsm_tester: specifics for running an Open%GS upfd process
#
# Copyright (C) 2021 by sysmocom - s.f.m.c. GmbH
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
    pass

class Open5gsUPF(log.Origin):

    REMOTE_DIR = '/osmo-gsm-tester-open5gs'
    BINFILE = 'open5gs-upfd'
    CFGFILE = 'open5gs-upfd.yaml'
    LOGFILE = 'open5gs-upfd.log'
    DIAMETERFILE = 'open5gs-freediameter.conf'
    O5GS_TUN_SETUP_BIN = 'osmo-gsm-tester_open5gs_tun_setup.sh'

    def __init__(self, testenv, o5gs_epc):
        super().__init__(log.C_RUN, 'open5gs-upfd')
        self.testenv = testenv
        self.o5gs_epc = o5gs_epc
        self._run_node = o5gs_epc.run_node()
        self.run_dir = None
        self.config_file = None
        self.log_file = None
        self.process = None
        self.rem_host = None
        self.remote_inst = None
        self.remote_config_file = None
        self.remote_log_file = None

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
        self.log('Starting %s' % Open5gsUPF.BINFILE)
        if self._run_node.is_local():
            self.start_locally()
        else:
            self.start_remotely()

    def start_remotely(self):
        remote_lib = self.remote_inst.child('lib')
        remote_binary = self.remote_inst.child('bin', Open5gsUPF.BINFILE)

        # setting capabilities will later disable use of LD_LIBRARY_PATH from ELF loader -> modify RPATH instead.
        self.log('Setting RPATH for open5gs-upfd')
        self.rem_host.change_elf_rpath(remote_binary, remote_lib)
        # open5gs-upfd requires CAP_NET_ADMIN to create tunnel devices: ioctl(TUNSETIFF):
        self.log('Applying CAP_NET_ADMIN capability to open5gs-upfd')
        self.rem_host.setcap_net_admin(remote_binary)

        args = (remote_binary, '-c', self.remote_config_file)
        remote_run_dir = util.Dir(util.Dir(Open5gsUPF.REMOTE_DIR).child(Open5gsUPF.BINFILE))

        self.process = self.rem_host.RemoteProcessSafeExit(Open5gsUPF.BINFILE, remote_run_dir, args)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def start_locally(self):
        binary = self.inst.child('bin', Open5gsUPF.BINFILE)
        lib = self.inst.child('lib')
        env = {}

        # setting capabilities will later disable use of LD_LIBRARY_PATH from ELF loader -> modify RPATH instead.
        self.log('Setting RPATH for open5gs-upfd')
        # open5gs-upfd binary needs patchelf <= 0.9 (0.10 and current master fail) to avoid failing during patch. OS#4389, patchelf-GH#192.
        util.change_elf_rpath(binary, util.prepend_library_path(lib), self.run_dir.new_dir('patchelf'))
        # open5gs-upfd requires CAP_NET_ADMIN to create tunnel devices: ioctl(TUNSETIFF):
        self.log('Applying CAP_NET_ADMIN capability to open5gs-upfd')
        util.setcap_net_admin(binary, self.run_dir.new_dir('setcap_net_admin'))

        args = (binary, '-c', os.path.abspath(self.config_file))

        self.process = process.Process(self.name(), self.run_dir, args, env=env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def configure(self, values):
        self.run_dir = util.Dir(self.o5gs_epc.run_dir.new_dir(self.name()))
        self.inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('open5gs', self._run_node.run_label())))
        if not os.path.isdir(self.inst.child('lib')):
            raise log.Error('No lib/ in', self.inst)
        if not self.inst.isfile('bin', Open5gsUPF.BINFILE):
            raise log.Error('No %s binary in' % Open5gsUPF.BINFILE, self.inst)

        self.config_file = self.run_dir.child(Open5gsUPF.CFGFILE)
        self.log_file = self.run_dir.child(Open5gsUPF.LOGFILE)

        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            remote_prefix_dir = util.Dir(Open5gsUPF.REMOTE_DIR)
            self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
            remote_run_dir = util.Dir(remote_prefix_dir.child(Open5gsUPF.BINFILE))

            self.remote_config_file = remote_run_dir.child(Open5gsUPF.CFGFILE)
            self.remote_log_file = remote_run_dir.child(Open5gsUPF.LOGFILE)

        logfile = self.log_file if self._run_node.is_local() else self.remote_log_file
        inst_prefix = str(self.inst) if self._run_node.is_local() else str(self.remote_inst)
        config.overlay(values, dict(upf=dict(log_filename=logfile,
                                             inst_prefix=inst_prefix)))

        self.dbg('OPEN5GS-UPF CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(Open5gsUPF.CFGFILE, values)
            self.dbg(r)
            f.write(r)

        if not self._run_node.is_local():
            self.rem_host.run_remote_sync('tun-setup', ('sudo', Open5gsUPF.O5GS_TUN_SETUP_BIN,
                                          self.o5gs_epc.tun_name(), self.o5gs_epc.tun_addr(),
                                          self.o5gs_epc.tun_netmask()))
            self.rem_host.recreate_remote_dir(self.remote_inst)
            self.rem_host.scp('scp-inst-to-remote', str(self.inst), remote_prefix_dir)
            self.rem_host.recreate_remote_dir(remote_run_dir)
            self.rem_host.scp('scp-cfg-to-remote', self.config_file, self.remote_config_file)

    def running(self):
        return not self.process.terminated()

# vim: expandtab tabstop=4 shiftwidth=4
