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

from ..core import log
from .rfemu import RFemulation
from .gnuradio_zmq_broker import GrBroker

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
