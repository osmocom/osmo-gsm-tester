# osmo_gsm_tester: OsmocomBB based Mobile Station (MS)
#
# Copyright (C) 2016-2019 by sysmocom - s.f.m.c. GmbH
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

from . import ms


class MSOsmoMobile(ms.MS):
    """Represent a osmocom-bb mobile."""

    def __init__(self, testenv, conf):
        super().__init__('ms_osmo', testenv, conf)

    def cleanup(self):
        # do nothing for a virtual resource
        pass

    def ki(self):
        ki = super().ki()
        if not ki:
            return "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"
        return ki

    def get_assigned_addr(self, ipv6=False):
        raise log.Error('API not implemented!')

    def is_registered(self, mcc_mnc=None):
        raise log.Error('API not implemented!')
