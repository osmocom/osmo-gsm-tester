# osmo_gsm_tester: specifics for running an Open5GS smfd process
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

class Open5gsSMF(log.Origin):

    REMOTE_DIR = '/osmo-gsm-tester-open5gs'
    BINFILE = 'open5gs-smfd'
    CFGFILE = 'open5gs-smfd.yaml'
    LOGFILE = 'open5gs-smfd.log'
    DIAMETERFILE = 'open5gs-freediameter.conf'

    def __init__(self, testenv, o5gs_epc):
        super().__init__(log.C_RUN, 'open5gs-smfd')
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
        self.log('Starting %s' % Open5gsSMF.BINFILE)
        if self._run_node.is_local():
            self.start_locally()
        else:
            self.start_remotely()

    def start_remotely(self):
        remote_env = { 'LD_LIBRARY_PATH': self.remote_inst.child('lib') }
        remote_lib = self.remote_inst.child('lib')
        remote_binary = self.remote_inst.child('bin', Open5gsSMF.BINFILE)

        args = (remote_binary, '-c', self.remote_config_file)
        remote_run_dir = util.Dir(util.Dir(Open5gsSMF.REMOTE_DIR).child(Open5gsSMF.BINFILE))

        self.process = self.rem_host.RemoteProcessSafeExit(Open5gsSMF.BINFILE, remote_run_dir, args, remote_env=remote_env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def start_locally(self):
        binary = self.inst.child('bin', Open5gsSMF.BINFILE)
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
        if not self.inst.isfile('bin', Open5gsSMF.BINFILE):
            raise log.Error('No %s binary in' % Open5gsSMF.BINFILE, self.inst)

        self.config_file = self.run_dir.child(Open5gsSMF.CFGFILE)
        self.log_file = self.run_dir.child(Open5gsSMF.LOGFILE)
        self.diameter_file = self.run_dir.child(Open5gsSMF.DIAMETERFILE)

        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            remote_prefix_dir = util.Dir(Open5gsSMF.REMOTE_DIR)
            self.remote_inst = util.Dir(remote_prefix_dir.child(os.path.basename(str(self.inst))))
            remote_run_dir = util.Dir(remote_prefix_dir.child(Open5gsSMF.BINFILE))

            self.remote_config_file = remote_run_dir.child(Open5gsSMF.CFGFILE)
            self.remote_log_file = remote_run_dir.child(Open5gsSMF.LOGFILE)
            self.remote_diameter_file = remote_run_dir.child(Open5gsSMF.DIAMETERFILE)

        logfile = self.log_file if self._run_node.is_local() else self.remote_log_file
        diameter_file = self.diameter_file if self._run_node.is_local() else self.remote_diameter_file
        inst_prefix = str(self.inst) if self._run_node.is_local() else str(self.remote_inst)
        config.overlay(values, dict(smf=dict(log_filename=logfile,
                                             diameter_filename=diameter_file,
                                             inst_prefix=inst_prefix)))
        config.overlay(values, dict(diameter=dict(identity=self.diameter_name(),
                                                  inst_prefix=inst_prefix,
                                                  listen_address=self.o5gs_epc.addr(),
                                                  listen_port=self.diameter_port(),
                                                  connect_name=self.o5gs_epc.pcrf.diameter_name(),
                                                  connect_address=self.o5gs_epc.addr(),
                                                  connect_port=self.o5gs_epc.pcrf.diameter_port())))

        self.dbg('OPEN5GS-SMF CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(Open5gsSMF.CFGFILE, values)
            self.dbg(r)
            f.write(r)

        with open(self.diameter_file, 'w') as f:
            r = template.render(Open5gsSMF.DIAMETERFILE, values)
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
        return 'smf'

    def diameter_port(self):
        return 3868 + 3;

# vim: expandtab tabstop=4 shiftwidth=4
