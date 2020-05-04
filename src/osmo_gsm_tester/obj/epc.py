# osmo_gsm_tester: base classes to share code among EPC subclasses.
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
from ..core import log, config
from ..core import schema

def on_register_schemas():
    config_schema = {
        'type': schema.STR,
        'qci': schema.UINT,
        }
    schema.register_config_schema('epc', config_schema)

class EPC(log.Origin, metaclass=ABCMeta):

##############
# PROTECTED
##############
    def __init__(self, suite_run, run_node, name):
        super().__init__(log.C_RUN, '%s' % name)
        self._addr = run_node.run_addr()
        self.set_name('%s_%s' % (name, self._addr))
        self.suite_run = suite_run
        self._run_node = run_node

    def configure(self, config_specifics_li):
        values = dict(epc=config.get_defaults('epc'))
        for config_specifics in config_specifics_li:
            config.overlay(values, dict(epc=config.get_defaults(config_specifics)))
        config.overlay(values, dict(epc=self.suite_run.config().get('epc', {})))
        for config_specifics in config_specifics_li:
            config.overlay(values, dict(epc=self.suite_run.config().get(config_specifics, {})))
        config.overlay(values, dict(epc={'run_addr': self.addr()}))
        return values

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
    def subscriber_add(self, modem, msisdn=None, algo_str=None):
        pass

    @abstractmethod
    def enb_is_connected(self, enb):
        pass

    @abstractmethod
    def running(self):
        pass

    @abstractmethod
    def tun_addr(self):
        pass

    def addr(self):
        return self._addr

    def run_node(self):
        return self._run_node

# vim: expandtab tabstop=4 shiftwidth=4
