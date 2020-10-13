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

from ..core import log
from .rfemu import RFemulation

class RFemulationSrsStdin(RFemulation):
##############
# PROTECTED
##############
    def __init__(self, conf):
        super().__init__(conf, 'srsenb_stdin')
        self.cell_id = int(conf.get('cell_id'))
        if self.cell_id is None:
            raise log.Error('No "cell_id" attribute provided in rfemu conf!')
        self.enb = conf.get('enb')
        if self.enb is None:
            raise log.Error('No "srsenb" attribute provided in rfemu conf!')

    def __del__(self):
        self.enb = None

#############################
# PUBLIC (test API included)
#############################
    def set_attenuation(self, db):
        msg_str = 'cell_gain %d %f' % (self.cell_id, -db)
        self.dbg('sending stdin msg: "%s"' % msg_str)
        self.enb.process.stdin_write(msg_str + '\n')

    def get_max_attenuation(self):
        return 200 # maximum cell_gain value in srs. Is this correct value?

# vim: expandtab tabstop=4 shiftwidth=4
