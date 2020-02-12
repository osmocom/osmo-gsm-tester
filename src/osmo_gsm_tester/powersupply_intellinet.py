# osmo_gsm_tester: class defining a Power Supply object
#
# Copyright (C) 2019 by sysmocom - s.f.m.c. GmbH
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

from . import log
from .powersupply import PowerSupply

class PowerSupplyIntellinet(PowerSupply):
    """PowerSupply implementation to controll Intellinet devices."""

    # HTTP request timeout, in seconds
    PDU_TIMEOUT = 5

    PDU_CMD_ON = 0
    PDU_CMD_OFF = 1

    def _url_prefix(self):
        return 'http://' + self.device_ip

    def _url_status(self):
        return self._url_prefix() + '/status.xml'

    def _url_set_port_status(self, pdu_cmd):
        return self._url_prefix() + "/control_outlet.htm?" + "outlet" + str(self.port - 1) + "=1" + "&op=" + str(pdu_cmd) + "&submit=Anwenden"

    def _port_stat_name(self):
        # Names start with idx 0, while in ogt we count sockets starting from 1.
        return 'outletStat' + str(self.port - 1)

    def _fetch_status(self):
        data = urllib.request.urlopen(self._url_status(), timeout = self.PDU_TIMEOUT).read()
        if not data:
            raise log.Error('empty status xml')
        return data

    def _get_port_status(self):
        data = self._fetch_status()
        root = ET.fromstring(data)
        for child in root:
            if child.tag == self._port_stat_name():
                return child.text
        raise log.Error('no state for %s' % self._port_stat_name())

    def _set_port_status(self, pdu_cmd):
        urllib.request.urlopen(self._url_set_port_status(pdu_cmd),timeout = self.PDU_TIMEOUT).read()


########################
# PUBLIC - INTERNAL API
########################
    def __init__(self, conf):
        super().__init__(conf, 'intellinet')
        mydevid = conf.get('device')
        if mydevid is None:
            raise log.Error('No "device" attribute provided in supply conf!')
        self.set_name('intellinet-'+mydevid)
        myport = conf.get('port')
        if myport is None:
            raise log.Error('No "port" attribute provided in power_supply conf!')
        if not int(myport):
            raise log.Error('Wrong non numeric "port" attribute provided in power_supply conf!')
        self.set_name('intellinet-'+mydevid+'-'+myport)
        self.device_ip = mydevid
        self.port = int(myport)

    def is_powered(self):
        """Get whether the device is powered on or off."""
        return self._get_port_status() == 'on'

    def power_set(self, onoff):
        """Turn on (onoff=True) or off (onoff=False) the device."""
        if onoff:
            self.dbg('switchon %s:%u' % (self.device_ip, self.port))
            self._set_port_status(self.PDU_CMD_ON)
        else:
            self.dbg('switchoff %s:%u' % (self.device_ip, self.port))
            self._set_port_status(self.PDU_CMD_OFF)


# vim: expandtab tabstop=4 shiftwidth=4
