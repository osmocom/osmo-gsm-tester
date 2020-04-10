# osmo_gsm_tester: class defining a Power Supply object
#
# Copyright (C) 2018-2019 by sysmocom - s.f.m.c. GmbH
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
from .core import log
from .core.event_loop import MainLoop

class PowerSupply(log.Origin, metaclass=ABCMeta):

##############
# PROTECTED
##############
    def __init__(self, conf, name):
        """Base constructor. Must be called by subclass."""
        super().__init__(log.C_RUN, name)
        self.conf = conf

########################
# PUBLIC - INTERNAL API
########################
    @abstractmethod
    def is_powered(self):
        """Get whether the device is powered on or off. Must be implemented by subclass."""
        pass

    @abstractmethod
    def power_set(self, onoff):
        """Turn on (onoff=True) or off (onoff=False) the device. Must be implemented by subclass."""
        pass

    def power_cycle(self, sleep=0):
        """Turns off the device, waits N.N seconds, then turn on the device."""
        self.power_set(False)
        MainLoop.sleep(self, sleep)
        self.power_set(True)


from . import powersupply_sispm, powersupply_intellinet

KNOWN_PWSUPPLY_TYPES = {
        'sispm' : powersupply_sispm.PowerSupplySispm,
        'intellinet' : powersupply_intellinet.PowerSupplyIntellinet,
}

def register_type(name, clazz):
    """Register a new PoerSupply child class at runtime."""
    KNOWN_PWSUPPLY_TYPES[name] = clazz

def get_instance_by_type(pwsupply_type, pwsupply_opt):
    """Allocate a PowerSupply child class based on type. Opts are passed to the newly created object."""
    obj = KNOWN_PWSUPPLY_TYPES.get(pwsupply_type, None)
    if not obj:
        raise log.Error('PowerSupply type not supported:', pwsupply_type)
    return obj(pwsupply_opt)



# vim: expandtab tabstop=4 shiftwidth=4
