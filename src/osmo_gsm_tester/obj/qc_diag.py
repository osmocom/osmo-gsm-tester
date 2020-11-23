# osmo_gsm_tester: specifics for running Qualcomm diagnostics on an AndroidUE modem
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

import getpass
import os
from ..core import remote, util, process, schema, log
from ..core.event_loop import MainLoop
from . import ms_android
from .android_host import AndroidHost
from .run_node import RunNode


def on_register_schemas():
    resource_schema = {}
    for key, val in ScatParser.schema().items():
        resource_schema['scat_parser.%s' % key] = val
    schema.register_resource_schema('modem', resource_schema)


class QcDiag(AndroidHost):

    DIAG_PARSER = 'osmo-gsm-tester_androidue_diag_parser.sh'

##############
# PROTECTED
##############
    def __init__(self, testenv, conf):
        self._run_node = RunNode.from_conf(conf.get('run_node', {}))
        super().__init__('qcdiag_%s' % self._run_node.run_addr())
        self.testenv = testenv
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr(), None,
                                              self._run_node.ssh_port())
            self.remote_run_dir = util.Dir(ms_android.AndroidUE.REMOTEDIR)
        self.scat_parser = ScatParser(testenv, conf)
        testenv.register_for_cleanup(self.scat_parser)
        self.diag_monitor_proc = None
        self.enable_pcap = util.str2bool(conf.get('enable_pcap', 'false'))

########################
# PUBLIC - INTERNAL API
########################
    def get_rrc_state(self):
        scat_parser_stdout_l = self.scat_parser.get_stdout().split('\n')
        # Find the first "Pulling new .qmdl file..." and check the state afterwards. This has to be done to
        # ensure that no process is reading the ScatParser's stdout while the parser is still writing to it.
        is_full_block = False
        for line in reversed(scat_parser_stdout_l):
            if 'Pulling new .qmdl file...' in line:
                is_full_block = True
            if is_full_block and 'LTE_RRC_STATE_CHANGE' in line:
                rrc_state = line.split(' ')[-1].replace('rrc_state=', '')
                rrc_state.replace('\'', '')
                return rrc_state
        return ''

    def get_paging_counter(self):
        diag_parser_stdout_l = self.scat_parser.get_stdout().split('\n')
        return diag_parser_stdout_l.count('Paging received')

    def running(self):
        return self.diag_monitor_proc.is_running()

    def write_pcap(self, restart=False):
        self.scat_parser.write_pcap(restart)

    def start(self):
        popen_args_diag = ['/vendor/bin/diag_mdlog', '-s', '90000', '-f', '/data/local/tmp/ogt_diag.cfg',
                           '-o', '/data/local/tmp/diag_logs']
        self.diag_monitor_proc = self.run_androidue_cmd('start-diag-monitor_%s' % self._run_node.adb_serial_id(), popen_args_diag)
        self.testenv.remember_to_stop(self.diag_monitor_proc)
        self.diag_monitor_proc.launch()

        self.scat_parser.configure(self._run_node, self.enable_pcap)
        self.scat_parser.start()

    def scp_back_pcap(self):
        self.scat_parser.scp_back_pcap()


class ScatParser(AndroidHost):
##############
# PROTECTED
##############
    def __init__(self, testenv, conf):
        self.testenv = testenv
        self._run_node = RunNode.from_conf(conf.get('scat_parser', {}))
        super().__init__('scat_parser_%s' % self._run_node.run_addr())
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.remote_run_dir = None
        self.rem_host = None
        self.pcap_file = None
        self.remote_pcap_file = None
        self.parser_proc = None
        self._parser_proc = None
        self.popen_args_diag_parser = None
        self._run_node_ue = None
        self.enable_pcap = False

    def _clear_diag_files(self):
        name_chown = 'chown-diag-files'
        diag_dir_local = str(self.run_dir) + '/diag_logs/'
        diag_dir_remote = str(self.remote_run_dir) + '/diag_logs/'
        popen_args_change_owner = ['sudo', 'chown', '-R', '', '']
        run_dir_chown = self.run_dir.new_dir(name_chown)
        if self._run_node.is_local():
            if os.path.exists(diag_dir_local):
                # Due to errors the diag_logs dir can be non-existing. To avoid errors the path
                # is checked for existence first.
                popen_args_change_owner[3] = getpass.getuser()
                popen_args_change_owner[4] = diag_dir_local
                change_owner_proc = process.Process(name_chown, run_dir_chown, popen_args_change_owner)
                change_owner_proc.launch_sync()
        else:
            popen_args_change_owner = ['sudo', 'chown', '-R', self.rem_host.user(), diag_dir_remote]
            change_owner_proc = self.rem_host.RemoteProcess(name_chown, popen_args_change_owner, remote_env={})
            change_owner_proc.launch_sync()

        name_clear = 'clear-diag-files'
        run_dir_clear = self.run_dir.new_dir(name_clear)
        popen_args_clear_diag_files = ['rm', '-r', '']
        if self._run_node.is_local():
            popen_args_clear_diag_files[2] = diag_dir_local
            clear_run_dir_proc = process.Process(name_clear, run_dir_clear, popen_args_clear_diag_files)
        else:
            popen_args_clear_diag_files[2] = diag_dir_remote
            clear_run_dir_proc = self.rem_host.RemoteProcess(name_clear, popen_args_clear_diag_files, remote_env={})
        clear_run_dir_proc.launch_sync()

########################
# PUBLIC - INTERNAL API
########################
    @classmethod
    def schema(cls):
        resource_schema = {
            'run_type': schema.STR,
            'run_addr': schema.IPV4,
            'ssh_user': schema.STR,
            'ssh_addr': schema.IPV4,
            'run_label': schema.STR,
            'ssh_port': schema.STR,
            'adb_serial_id': schema.STR,
            }
        return resource_schema

    def configure(self, run_node, enable_pcap):
        self.enable_pcap = enable_pcap
        self._run_node_ue = run_node

        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            self.remote_run_dir = util.Dir(ms_android.AndroidUE.REMOTEDIR)
            self.remote_pcap_file = self.remote_run_dir.child(ms_android.AndroidUE.PCAPFILE)
        self.pcap_file = self.run_dir.child(ms_android.AndroidUE.PCAPFILE)

    def start(self):
        # format: osmo-gsm-tester_androidue_diag_parser.sh $serial $run_dir $pcap_path $remote_ip $remote_port
        self.popen_args_diag_parser = [QcDiag.DIAG_PARSER, '', '', '', '', '']
        if self._run_node_ue.is_local():
            if not self._run_node.is_local():
                # AndroidUE is attached to Master but ScatParser is running remote
                raise log.Error('Running the network locally and the ScatParser remotely is currently not supported')
            else:
                # Master, ScatParser, and AndroidUE are attached to/running on the same host
                self.popen_args_diag_parser[1] = str(self._run_node.adb_serial_id())    # adb serial
                self.popen_args_diag_parser[2] = str(self.run_dir)                      # run dir path
                self.popen_args_diag_parser[3] = str(self.pcap_file)                    # pcap file path
                self.popen_args_diag_parser[4] = '0'                                    # remote ip
                self.popen_args_diag_parser[5] = '0'                                    # remote port
        else:
            if self._run_node.is_local():
                # Master and ScatParser running on the same machine, the AndroidUE runs remote
                self.popen_args_diag_parser[1] = '0'                                    # adb serial
                self.popen_args_diag_parser[2] = str(self.run_dir)                      # run dir path
                self.popen_args_diag_parser[3] = str(self.pcap_file)                    # pcap file path
                self.popen_args_diag_parser[4] = str(self._run_node_ue.ssh_addr())      # remote ip AndroidUE
                self.popen_args_diag_parser[5] = str(self._run_node_ue.ssh_port())      # remote port AndroidUE
            elif self._run_node.ssh_addr() == self._run_node_ue.ssh_addr():
                # ScatParser and AndroidUE are remote but on the same machine
                self.popen_args_diag_parser[1] = str(self._run_node.adb_serial_id())    # adb serial
                self.popen_args_diag_parser[2] = str(self.remote_run_dir)               # run dir path
                self.popen_args_diag_parser[3] = str(self.remote_pcap_file)             # pcap file path
                self.popen_args_diag_parser[4] = '0'                                    # remote ip
                self.popen_args_diag_parser[5] = '0'                                    # remote port
            else:
                # Master, ScatParser and AndroidUE are running on/attached to different machines
                self.popen_args_diag_parser[1] = '0'                                    # adb serial
                self.popen_args_diag_parser[2] = str(self.remote_run_dir)               # run dir path
                self.popen_args_diag_parser[3] = str(self.remote_pcap_file)             # pcap file path
                self.popen_args_diag_parser[4] = str(self._run_node_ue.ssh_addr())      # remote ip AndroidUE
                self.popen_args_diag_parser[5] = str(self._run_node_ue.ssh_port())      # remote port AndroidUE

        if not self._run_node.is_local():
            # The diag_logs directory only exists here if the ScatParser entity is running remote
            self._clear_diag_files()

        name = 'scat_parser_%s' % self._run_node.run_addr()
        if self._run_node.is_local():
            run_dir = self.run_dir.new_dir(name)
            self.parser_proc = process.Process(name, run_dir, self.popen_args_diag_parser)
        else:
            self.parser_proc = self.rem_host.RemoteProcess(name, self.popen_args_diag_parser, remote_env={})
        self.testenv.remember_to_stop(self.parser_proc)
        self.parser_proc.launch()

    def stop(self):
        self.testenv.stop_process(self.parser_proc)

    def write_pcap(self, restart=False):
        # We need to stop the diag_parser to avoid pulling a new .qmdl during
        # the parsing process. The process can be restarted afterwards but keep in
        # mind that this will overwrite the pcap after some time. The diag_monitor
        # process can continue, as it does not hinder this process.
        if self.parser_proc and self.parser_proc.is_running():
            self.testenv.stop_process(self.parser_proc)
        self._clear_diag_files()

        name = 'write-pcap_%s' % self._run_node.run_addr()
        if self._run_node.is_local():
            run_dir = self.run_dir.new_dir(name)
            self._parser_proc = process.Process(name, run_dir, self.popen_args_diag_parser)
        else:
            self._parser_proc = self.rem_host.RemoteProcess(name, self.popen_args_diag_parser, remote_env={})
        self.testenv.remember_to_stop(self._parser_proc)
        self._parser_proc.launch()

        MainLoop.wait(self.finished_parsing, timestep=0.1, timeout=300)

        if restart:
            self.parser_proc = self._parser_proc
        else:
            self.testenv.stop_process(self._parser_proc)

    def finished_parsing(self):
        scat_parser_stdout = self._parser_proc.get_stdout()
        # If the parsers pulls the .qmdl file for the second time we know that
        # the parsing of the first one is done
        return scat_parser_stdout.count('Pulling new .qmdl file...') > 1

    def get_stdout(self):
        return self.parser_proc.get_stdout()

    def is_running(self):
        return self.parser_proc.is_running()

    def scp_back_pcap(self):
        try:
            self.rem_host.scpfrom('scp-back-pcap', self.remote_pcap_file, self.pcap_file)
        except Exception as e:
            self.log(repr(e))

    def cleanup(self):
        if self.enable_pcap:
            self.write_pcap(restart=False)
            if not self._run_node.is_local():
                self.scp_back_pcap()
