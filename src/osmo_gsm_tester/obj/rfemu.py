# osmo_gsm_tester: class defining a RF emulation object
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

from abc import ABCMeta, abstractmethod
from ..core import log
from ..core.event_loop import MainLoop

class RFemulation(log.Origin, metaclass=ABCMeta):

##############
# PROTECTED
##############
    def __init__(self, conf, name):
        """Base constructor. Must be called by subclass."""
        super().__init__(log.C_RUN, name)
        self.conf = conf

#############################
# PUBLIC (test API included)
#############################
    @abstractmethod
    def set_attenuation(self, db):
        """Set attenuation in dB on the configured channel"""
        pass

def get_instance_by_type(rfemu_type, rfemu_opt):
    """Allocate a RFemulation child class based on type. Opts are passed to the newly created object."""
    if rfemu_type == 'amarisoftctl':
        from .rfemu_amarisoftctrl import RFemulationAmarisoftCtrl
        obj = RFemulationAmarisoftCtrl
    elif rfemu_type == 'minicircuits':
        from .rfemu_minicircuits import RFemulationMinicircuitsHTTP
        obj = RFemulationMinicircuitsHTTP
    else:
        raise log.Error('RFemulation type not supported:', rfemu_type)

    return obj(rfemu_opt)



# vim: expandtab tabstop=4 shiftwidth=4
