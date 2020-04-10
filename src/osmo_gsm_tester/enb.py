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
from .core import log, config


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
        self._txmode = 0
        self._num_prb = 0
        self._epc = None

    def configure(self, config_specifics_li):
        values = dict(enb=config.get_defaults('enb'))
        for config_specifics in config_specifics_li:
            config.overlay(values, dict(enb=config.get_defaults(config_specifics)))
        config.overlay(values, dict(enb=self.suite_run.config().get('enb', {})))
        for config_specifics in config_specifics_li:
            config.overlay(values, dict(enb=self.suite_run.config().get(config_specifics, {})))
        config.overlay(values, dict(enb=self._conf))
        self._num_prb = int(values['enb'].get('num_prb', None))
        assert self._num_prb
        self._txmode = int(values['enb'].get('transmission_mode', None))
        assert self._txmode
        config.overlay(values, dict(enb={ 'num_ports': self.num_ports() }))
        assert self._epc is not None
        config.overlay(values, dict(enb={ 'mme_addr': self._epc.addr() }))
        return values

    def num_ports(self):
        if self._txmode == 1:
            return 1
        return 2

########################
# PUBLIC - INTERNAL API
########################
    def cleanup(self):
        'Nothing to do by default. Subclass can override if required.'
        pass

    def num_prb(self):
        return self._num_prb

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

    def ue_max_rate(self, downlink=True):
        # The max rate for a single UE per PRB configuration in TM1
        max_phy_rate_tm1_dl = { 6 : 3.5e6,
                               15 : 11e6,
                               25 : 18e6,
                               50 : 36e6,
                               75 : 55e6,
                               100 : 75e6 }
        max_phy_rate_tm1_ul = { 6 : 0.9e6,
                               15 : 4.7e6,
                               25 : 10e6,
                               50 : 23e6,
                               75 : 34e6,
                               100 : 51e6 }
        if downlink:
            max_rate = max_phy_rate_tm1_dl[self.num_prb()]
        else:
            max_rate = max_phy_rate_tm1_ul[self.num_prb()]
        #TODO: calculate for non-standard prb numbers.
        if self._txmode > 2:
            max_rate *= 2
        # We use 3 control symbols for 6, 15 and 25 PRBs which results in lower max rate
        if self.num_prb() < 50:
          max_rate *= 0.9
        return max_rate

# vim: expandtab tabstop=4 shiftwidth=4
