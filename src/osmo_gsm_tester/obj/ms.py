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
from ..core import log
from ..core import schema

def on_register_schemas():
    resource_schema = {
        'type': schema.STR,
        'label': schema.STR,
        'path': schema.STR,
        'imsi': schema.IMSI,
        'ki': schema.KI,
        'auth_algo': schema.AUTH_ALGO,
        'apn_ipaddr': schema.IPV4,
        'ciphers[]': schema.CIPHER,
        'features[]': schema.MODEM_FEATURE
        }
    schema.register_resource_schema('modem', resource_schema)

class MS(log.Origin, metaclass=ABCMeta):
    """Base for everything about mobile/modem and SIMs."""

##############
# PROTECTED
##############
    def __init__(self, name, conf):
        super().__init__(log.C_TST, name)
        self._conf = conf
        self.msisdn = None

########################
# PUBLIC - INTERNAL API
########################
    @abstractmethod
    def cleanup(self):
        """Cleans up resources allocated."""
        pass

    def get_instance_by_type(testenv, conf):
        """Allocate a MS child class based on type. Opts are passed to the newly created object."""
        ms_type = conf.get('type')
        if ms_type is None:
            # Map None to ofono for forward compability
            ms_type = 'ofono'

        if ms_type == 'ofono':
            from .ms_ofono import Modem
            ms_class = Modem
        elif ms_type == 'osmo-mobile':
            from .ms_osmo_mobile import MSOsmoMobile
            ms_class = MSOsmoMobile
        elif ms_type == 'srsue':
            from .ms_srs import srsUE
            ms_class = srsUE
        elif ms_type == 'amarisoftue':
            from .ms_amarisoft import AmarisoftUE
            ms_class = AmarisoftUE
        else:
            raise log.Error('MS type not supported:', ms_type)
        return ms_class(testenv, conf)

###################
# PUBLIC (test API included)
###################
    def imsi(self):
        return self._conf.get('imsi')

    def ki(self):
        return self._conf.get('ki')

    def apn_ipaddr(self):
        return self._conf.get('apn_ipaddr', 'dynamic')

    def auth_algo(self):
        return self._conf.get('auth_algo', None)

    def set_msisdn(self, msisdn):
        self.msisdn = msisdn

    def msisdn(self):
        return self.msisdn

    def get_counter(self, counter_name):
        raise log.Error('get_counter() not implemented!')
