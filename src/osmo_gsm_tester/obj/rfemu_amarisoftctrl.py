# osmo_gsm_tester: class defining a RF emulation object implemented using Amarisoft Ctl interface
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

from ..core import log
from .rfemu import RFemulation

class RFemulationAmarisoftCtrl(RFemulation):
##############
# PROTECTED
##############
    def __init__(self, conf):
        super().__init__(conf, 'amarisoftctl')
        self.addr = conf.get('addr')
        self.port = conf.get('ports')
        if self.addr is None:
            raise log.Error('No "addr" attribute provided in supply conf!')
        if self.port is None or len(self.port) != 1:
            raise log.Error('No "port" attribute provided in supply conf!')
        self.port = self.port[0]
        self.set_name('amarisoftctl(%s:%d)' % (self.addr, self.port))
        self.cell_id = conf.get('cell_id')
        if self.cell_id is None:
            raise log.Error('No "cell_id" attribute provided in supply conf!')

        from websocket import create_connection
        self.ws = create_connection("ws://%s:%s" % (self.addr, self.port))

    def __del__(self):
        self.dbg('closing CTRL websocket')
        self.ws.close()

#############################
# PUBLIC (test API included)
#############################
    def set_attenuation(self, db):
        msg = { "message": "cell_gain", "cell_id": int(self.cell_id), "gain": -db }
        msg_str = json.dumps(msg)
        self.dbg('sending CTRL msg: "%s"' % msg_str)
        self.ws.send(msg_str)
        self.dbg('waiting CTRL recv...')
        result = self.ws.recv()
        self.dbg('Received CTRL msg: "%s"' % result)

    def get_max_attenuation(self):
        return 200 # maximum cell_gain value in Amarisoft

# vim: expandtab tabstop=4 shiftwidth=4
