# osmo_gsm_tester: class defining a RF emulation object implemented using a Minicircuits RC4DAT-6G-60 device
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

import urllib.request
import xml.etree.ElementTree as ET

from ..core import log
from .rfemu import RFemulation

# https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf
class RFemulationMinicircuitsHTTP(RFemulation):

    # HTTP request timeout, in seconds
    HTTP_TIMEOUT = 5

##############
# PROTECTED
##############
    def __init__(self, conf):
        super().__init__(conf, 'minicircuits')
        self.addr = conf.get('addr')
        self.ports = conf.get('ports')
        if self.addr is None:
            raise log.Error('No "addr" attribute provided in supply conf!')
        if self.ports is None or len(self.ports) == 0:
            raise log.Error('No "port" attribute provided in supply conf!')
        self.set_name('minicircuits(%s:%r)' % (self.addr, self.ports))

    def _url_prefix(self):
        #http://10.12.1.216/:SetAttPerChan:1:0_2:0_3:0_4:0
        return 'http://' + self.addr

    def _utl_set_attenauation(self, db):
        ports_str = ""
        for port in self.ports:
            ports_str = ports_str + str(port) + ":"

        return self._url_prefix() + '/:CHAN:' + ports_str + 'SETATT:' + str(db)

#############################
# PUBLIC (test API included)
#############################
    def set_attenuation(self, db):
        url = self._utl_set_attenauation(db)
        self.dbg('sending HTTP req: "%s"' % url)
        data = urllib.request.urlopen(url, timeout = self.HTTP_TIMEOUT).read()
        data_str = str(data, 'utf-8')
        self.dbg('Received response: "%s"' % data_str)
        if data_str != '1':
            raise log.Error('Mini-circuits attenuation device returned failure! %s' & data_str)

    def get_max_attenuation(self):
        return 95 # Maximum value of the Mini-Circuits RC4DAT-6G-95

# vim: expandtab tabstop=4 shiftwidth=4
