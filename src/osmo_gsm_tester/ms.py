# osmo_gsm_tester: Base class for Mobile Stations (MS)
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
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

from abc import ABCMeta, abstractmethod
from . import log

class MS(log.Origin, metaclass=ABCMeta):
    """Base for everything about mobile/modem and SIMs."""

    def __init__(self, name, conf):
        super().__init__(log.C_TST, name)
        self._conf = conf
        self.msisdn = None

    def imsi(self):
        return self._conf.get('imsi')

    def ki(self):
        return self._conf.get('ki')

    def auth_algo(self):
        return self._conf.get('auth_algo', None)

    def set_msisdn(self, msisdn):
        self.msisdn = msisdn

    def msisdn(self):
        return self.msisdn

    @abstractmethod
    def cleanup(self):
        """Cleans up resources allocated."""
        pass