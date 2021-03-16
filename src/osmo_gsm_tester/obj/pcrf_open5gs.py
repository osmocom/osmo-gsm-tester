# osmo_gsm_tester: specifics for running an Open5GS pcrfd process
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

class Open5gsPCRF(log.Origin):

    REMOTE_DIR = '/osmo-gsm-tester-open5gs'
    BINFILE = 'open5gs-pcrfd'
    CFGFILE = 'open5gs-pcrfd.yaml'
    LOGFILE = 'open5gs-pcrfd.log'
    DIAMETERFILE = 'open5gs-freediameter.conf'

    def __init__(self, testenv, o5gs_epc):
        super().__init__(log.C_RUN, 'open5gs-pcrfd')
        self.testenv = testenv
        self.o5gs_epc = o5gs_epc
        self._run_node = o5gs_epc.run_node()
        self.run_dir = None
        self.config_file = None
        self.log_file = None
        self.diameter_file = None
        self.process = None
        self.rem_host = None
        self.remote_inst = None
        self.remote_config_file = None
        self.remote_log_file = None
        self.remote_diameter_file = None

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
        self.log('Starting %s' % Open5gsPCRF.BINFILE)
        if self._run_node.is_local():
            self.start_locally()
        else:
            self.start_remotely()

    def start_remotely(self):
        remote_env = { 'LD_LIBRARY_PATH': self.remote_inst.child('lib') }
        remote_lib = self.remote_inst.child('lib')
        remote_binary = self.remote_inst.child('bin', Open5gsPCRF.BINFILE)

        args = (remote_binary, '-c', self.remote_config_file)

        self.process = self.rem_host.RemoteProcess(Open5gsPCRF.BINFILE, args, remote_env=remote_env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def start_locally(self):
        binary = self.inst.child('bin', Open5gsPCRF.BINFILE)
        lib = self.inst.child('lib')
        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        args = (binary, '-c', os.path.abspath(self.config_file))

        self.process = process.Process(self.name(), self.run_dir, args, env=env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def configure(self, values):
        self.run_dir = util.Dir(self.o5gs_epc.run_dir.new_dir(self.name()))
        self.inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('open5gs', self._run_node.run_label())))
        if not os.path.isdir(self.inst.child('lib')):
            raise log.Error('No lib/ in', self.inst)
        if not self.inst.isfile('bin', Open5gsPCRF.BINFILE):
            raise log.Error('No %s binary in' % Open5gsPCRF.BINFILE, self.inst)

        self.config_file = self.run_dir.child(Open5gsPCRF.CFGFILE)
        self.log_file = self.run_dir.child(Open5gsPCRF.LOGFILE)
        self.diameter_file = self.run_dir.child(Open5gsPCRF.DIAMETERFILE)

        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            remote_prefix_dir = util.Dir(Open5gsPCRF.REMOTE_DIR)
            self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
            remote_run_dir = util.Dir(remote_prefix_dir.child(Open5gsPCRF.BINFILE))

            self.remote_config_file = remote_run_dir.child(Open5gsPCRF.CFGFILE)
            self.remote_log_file = remote_run_dir.child(Open5gsPCRF.LOGFILE)
            self.remote_diameter_file = remote_run_dir.child(Open5gsPCRF.DIAMETERFILE)

        logfile = self.log_file if self._run_node.is_local() else self.remote_log_file
        diameter_file = self.diameter_file if self._run_node.is_local() else self.remote_diameter_file
        inst_prefix = str(self.inst) if self._run_node.is_local() else str(self.remote_inst)
        config.overlay(values, dict(pcrf=dict(log_filename=logfile,
                                             diameter_filename=diameter_file,
                                             inst_prefix=inst_prefix)))
        config.overlay(values, dict(diameter=dict(identity=self.diameter_name(),
                                                  inst_prefix=inst_prefix,
                                                  listen_address=self.o5gs_epc.addr(),
                                                  listen_port=self.diameter_port(),
                                                  connect_name=self.o5gs_epc.smf.diameter_name(),
                                                  connect_address=self.o5gs_epc.addr(),
                                                  connect_port=self.o5gs_epc.smf.diameter_port())))

        self.dbg('OPEN5GS-PCRF CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(Open5gsPCRF.CFGFILE, values)
            self.dbg(r)
            f.write(r)

        with open(self.diameter_file, 'w') as f:
            r = template.render(Open5gsPCRF.DIAMETERFILE, values)
            self.dbg(r)
            f.write(r)

        if not self._run_node.is_local():
            self.rem_host.recreate_remote_dir(self.remote_inst)
            self.rem_host.scp('scp-inst-to-remote', str(self.inst), remote_prefix_dir)
            self.rem_host.recreate_remote_dir(remote_run_dir)
            self.rem_host.scp('scp-cfg-to-remote', self.config_file, self.remote_config_file)
            self.rem_host.scp('scp-diam-to-remote', self.diameter_file, self.remote_diameter_file)

    def running(self):
        return not self.process.terminated()

    def diameter_name(self):
        return 'pcrf'

    def diameter_port(self):
        return 3868 + 2;

# vim: expandtab tabstop=4 shiftwidth=4
