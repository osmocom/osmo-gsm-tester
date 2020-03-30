# osmo_gsm_tester: base classes to share code among eNodeB subclasses.
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
from . import log


class eNodeB(log.Origin, metaclass=ABCMeta):

##############
# PROTECTED
##############
    def __init__(self, suite_run, conf, name):
        super().__init__(log.C_RUN, '%s' % name)
        self._conf = conf
        self._addr = conf.get('addr', None)
        if self._addr is None:
            raise log.Error('addr not set')
        self.set_name('%s_%s' % (name, self._addr))

########################
# PUBLIC - INTERNAL API
########################
    def cleanup(self):
        'Nothing to do by default. Subclass can override if required.'
        pass

###################
# PUBLIC (test API included)
###################
    @abstractmethod
    def start(self, epc):
        'Starts ENB, it will connect to "epc"'
        pass

    @abstractmethod
    def ue_add(self, ue):
        pass

    @abstractmethod
    def running(self):
        pass

    @abstractmethod
    def ue_max_rate(self, downlink=True):
        pass

    def addr(self):
        return self._addr

# vim: expandtab tabstop=4 shiftwidth=4
