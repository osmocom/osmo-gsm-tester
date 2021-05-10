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
    def __init__(self, testenv, run_node, name):
        super().__init__(log.C_RUN, '%s' % name)
        self._addr = run_node.run_addr()
        self.set_name('%s_%s' % (name, self._addr))
        self.testenv = testenv
        self._run_node = run_node

    def configure(self, config_specifics_li):
        values = dict(epc=config.get_defaults('epc'))
        for config_specifics in config_specifics_li:
            config.overlay(values, dict(epc=config.get_defaults(config_specifics)))
        config.overlay(values, dict(epc=self.testenv.suite().config().get('epc', {})))
        for config_specifics in config_specifics_li:
            config.overlay(values, dict(epc=self.testenv.suite().config().get(config_specifics, {})))
        config.overlay(values, dict(epc={'run_addr': self.addr()}))
        return values

########################
# PUBLIC - INTERNAL API
########################
    def cleanup(self):
        'Nothing to do by default. Subclass can override if required.'
        pass

    def get_instance_by_type(testenv, run_node):
        """Allocate a EPC child class based on type. Opts are passed to the newly created object."""
        values = dict(epc=config.get_defaults('epc'))
        config.overlay(values, dict(epc=testenv.suite().config().get('epc', {})))
        epc_type = values['epc'].get('type', None)
        if epc_type is None:
            raise RuntimeError('EPC type is not defined!')

        if epc_type == 'amarisoftepc':
            from .epc_amarisoft import AmarisoftEPC
            epc_class = AmarisoftEPC
        elif epc_type == 'srsepc':
            from .epc_srs import srsEPC
            epc_class = srsEPC
        elif epc_type == 'open5gs':
            from .epc_open5gs import Open5gsEPC
            epc_class = Open5gsEPC
        else:
            raise log.Error('EPC type not supported:', epc_type)

        return  epc_class(testenv, run_node)

    def prepare_process(self, name, popen_args):
        ''' Prepare and return a process to run on EPC node.
            Caller calls either launch() or launch_sync()
            for non-blocking or blocking operation respectively '''
        if self._run_node.is_local():
            proc = process.Process(name, self.run_dir, popen_args)
        else:
            proc = self.rem_host.RemoteProcess(name, popen_args)
        return proc

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

    @abstractmethod
    def get_kpis(self):
        pass

# vim: expandtab tabstop=4 shiftwidth=4
