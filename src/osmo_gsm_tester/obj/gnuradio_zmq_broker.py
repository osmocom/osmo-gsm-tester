# osmo_gsm_tester: class defining a RF emulation object implemented using SRS ENB stdin interface
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

import json
import socket
import os

from ..core import log
from ..core import util
from ..core import process
from ..core import remote
from ..core.event_loop import MainLoop

class GrBroker(log.Origin):

    # static fields:
    refcount = 0
    instance = None

    REMOTE_DIR = '/osmo-gsm-tester-grbroker'
    TGT_SCRIPT_NAME = 'gnuradio_zmq_broker_remote.py' # File located in same directory as thine one
    TGT_SCRIPT_LOCAL_PATH = os.path.join(util.external_dir(), TGT_SCRIPT_NAME)

    def __init__(self):
        super().__init__(log.C_RUN, 'gr_zmq_broker')
        self.process = None
        self.ctrl_port = 5005
        self.run_dir = None
        self._run_node = None
        self.rem_host = None
        self.remote_run_dir = None
        self.remote_tgt_script = None
        self.enb_li = []
        self.ctrl_sk = None
        self.num_enb_started = 0

    @staticmethod
    def ref():
        if GrBroker.refcount == 0:
            GrBroker.instance = GrBroker()
        GrBroker.refcount = GrBroker.refcount + 1
        return GrBroker.instance

    @staticmethod
    def unref():
        GrBroker.refcount = GrBroker.refcount - 1
        if GrBroker.refcount == 0:
            GrBroker.instance.cleanup()
            GrBroker.instance = None

    def cleanup(self):
        if self.ctrl_sk is not None:
            self.cmd_exit()
            self.ctrl_sk.close()
            self.ctrl_sk = None
        self.enb_li = []
        self.testenv = None

    def register_enb(self, enb):
        if len(self.enb_li) == 0:
            # The gnuradio script is run on the first ENB host/addr.
            self._run_node = enb._run_node
        self.enb_li.append(enb)

    def unregister_enb(self, enb):
        self.enb_li.remove(enb)

    def addr(self):
        return self._run_node.run_addr()

    def gen_json_enb(self, enb):
        res = []
        cell_list = enb.gen_conf['enb']['cell_list']
        for cell in cell_list:
            # TODO: probably add enb_id, cell_id to support several ENB
            data = {'earfcn': int(cell['dl_earfcn']),
                    'bind_port': int(cell['zmq_enb_peer_port']),
                    'peer_addr': enb.addr(),
                    'peer_port': int(cell['zmq_enb_bind_port']),
                    'use_mimo': True if enb.num_ports() > 1 else False
                    }
            res.append(data)
        return res

    def gen_json_ue(self, enb):
        res = {}
        res = []
        earfcns_done = []
        cell_list = enb.gen_conf['enb']['cell_list']
        for cell in cell_list:
            data = {}
            if int(cell['dl_earfcn']) in earfcns_done:
                continue
            earfcns_done.append(int(cell['dl_earfcn']))
            data = {'earfcn': int(cell['dl_earfcn']),
                    'bind_port': int(cell['zmq_ue_peer_port']),
                    'peer_addr': enb.ue.addr(),
                    'peer_port': int(cell['zmq_ue_bind_port']),
                    'use_mimo': True if enb.num_ports() > 1 else False
                    }
            res.append(data)
        return res

    def gen_json(self):
        res = {'enb': [self.gen_json_enb(enb) for enb in self.enb_li],
               'ue': [self.gen_json_ue(self.enb_li[0])]}
        return res

    def configure(self):
        self.testenv = self.enb_li[0].testenv
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        if not self._run_node.is_local():
            self.rem_host = remote.RemoteHost(self.run_dir, self._run_node.ssh_user(), self._run_node.ssh_addr())
            remote_prefix_dir = util.Dir(GrBroker.REMOTE_DIR)
            self.remote_run_dir = util.Dir(remote_prefix_dir.child(self.name()))
            self.remote_tgt_script = os.path.join(str(self.remote_run_dir), GrBroker.TGT_SCRIPT_NAME)
            self.rem_host.recreate_remote_dir(self.remote_run_dir)
            self.rem_host.scp('scp-grboker-to-remote', GrBroker.TGT_SCRIPT_LOCAL_PATH, self.remote_tgt_script)

    def start(self):
        self.num_enb_started += 1
        self.dbg('start(%d/%d)' % (self.num_enb_started, len(self.enb_li)))
        if self.num_enb_started == 1:
            self.configure()
            if self._run_node.is_local():
                args = (GrBroker.TGT_SCRIPT_LOCAL_PATH,
                        '-c', str(self.ctrl_port),
                        '-b', self.addr())
                self.process = process.Process(self.name(), self.run_dir, args)
            else:
                args = (self.remote_tgt_script,
                        '-c', str(self.ctrl_port),
                        '-b', self.addr())
                self.process = self.rem_host.RemoteProcessSafeExit(self.name(), self.remote_run_dir, args, wait_time_sec=7)
            self.testenv.remember_to_stop(self.process)
            self.process.launch()
        # Wait until all ENBs are configured/started:
        if self.num_enb_started == len(self.enb_li):
            self.dbg('waiting for gr script to be available...')
            MainLoop.sleep(5)
            self.ctrl_sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.cmd_setup()

    def send_cmd(self, str_buf):
        self.dbg('sending cmd: "%s"' % str_buf)
        self.ctrl_sk.sendto(str_buf.encode('utf-8'), (self.addr(), self.ctrl_port))

    def cmd_setup(self):
        cfg = self.gen_json()
        buf = json.dumps(cfg)
        self.send_cmd(buf)

    def cmd_set_relative_gain_on_local_port(self, port, rel_gain):
        d = { 'action': 'set_relative_gain',
              'port': port,
              'rel_gain': rel_gain
            }
        buf = json.dumps(d)
        self.send_cmd(buf)

    def cmd_exit(self):
        d = { 'action': 'exit' }
        buf = json.dumps(d)
        self.send_cmd(buf)
