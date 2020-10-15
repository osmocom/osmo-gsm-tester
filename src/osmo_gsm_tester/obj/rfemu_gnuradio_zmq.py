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

from ..core import log
from ..core import util
from ..core import process
from ..core import remote
from ..core.event_loop import MainLoop
from .rfemu import RFemulation


class GrBroker(log.Origin):

    # static fields:
    refcount = 0
    instance = None

    def __init__(self):
        super().__init__(log.C_RUN, 'zmq_gr_broker')
        self.process = None
        self.ctrl_port = 5005
        self.run_dir = None
        self.rem_host = None
        self.cfg = None
        self.enb = None
        self.addr = None
        self.ctrl_sk = None

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
        self.enb = None
        self.testenv = None

    def handle_enb(self, enb):
        self.enb = enb
        self.addr = self.enb.addr()
        self.testenv = self.enb.testenv
        self.cfg = self.gen_json(enb)
        # FIXME: we may need to delay this somehow if we want to support several ENBs
        self.start()
        self.setup()

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

    def gen_json(self, enb):
        res = {'enb': [self.gen_json_enb(enb)],
               'ue': [self.gen_json_ue(enb)]}
        return res

    def start(self):
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))

        args = ('osmo-gsm-tester_zmq_broker.py',
                '-c', str(self.ctrl_port),
                '-b', self.enb.addr())

        if self.enb._run_node.is_local():
            self.process = process.Process(self.name(), self.run_dir, args)
        else:
            self.rem_host = remote.RemoteHost(self.run_dir, self.enb._run_node.ssh_user(), self.enb._run_node.ssh_addr())
            self.process = self.rem_host.RemoteProcessSafeExit('zmq_gr_broker', util.Dir('/tmp/ogt_%s' % self.name()), args, wait_time_sec=7)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def setup(self):
        self.dbg('waiting for gr script to be available...')
        MainLoop.sleep(5)
        self.ctrl_sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        buf = json.dumps(self.cfg)
        self.send_cmd(buf)

    def send_cmd(self, str_buf):
        self.dbg('sending cmd: "%s"' % str_buf)
        self.ctrl_sk.sendto(str_buf.encode('utf-8'), (self.addr, self.ctrl_port))

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

class RFemulationGnuradioZmq(RFemulation):
##############
# PROTECTED
##############
    def __init__(self, conf):
        super().__init__(conf, 'gnuradio_zmq')
        self.broker = None
        self.ctrl_port = 5005
        self.cell_id = int(conf.get('cell_id'))
        if self.cell_id is None:
            raise log.Error('No "cell_id" attribute provided in rfemu conf!')
        self.enb = conf.get('enb')
        if self.enb is None:
            raise log.Error('No "srsenb" attribute provided in rfemu conf!')
        self.set_name('%s_%s_%d' % (self.name(), self.enb.name(), self.cell_id))
        self.testenv = self.enb.testenv
        self.configure()

    def __del__(self):
        if self.broker:
            self.broker.unref()
            self.broker = None
        self.enb = None
        self.testenv = None

    def configure(self):
        self.broker = GrBroker.ref()

#############################
# PUBLIC (test API included)
#############################
    def set_attenuation(self, db):
        for cell in self.enb.gen_conf['enb']['cell_list']:
            if int(cell['cell_id']) == self.cell_id:
                # convert negative dB to amplitude
                amp = pow(10, -db/20.0)
                self.broker.cmd_set_relative_gain_on_local_port(cell['zmq_enb_peer_port'], amp)
                break

    def get_max_attenuation(self):
        return 200

# vim: expandtab tabstop=4 shiftwidth=4
