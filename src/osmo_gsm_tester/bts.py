# osmo_gsm_tester: base classes to share code among BTS subclasses.
#
# Copyright (C) 2018 by sysmocom - s.f.m.c. GmbH
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

import os
import pprint
import tempfile
from abc import ABCMeta, abstractmethod
from . import log, config, util, template, process, pcu_osmo

class Bts(log.Origin, metaclass=ABCMeta):
    suite_run = None
    conf = None
    bsc = None
    sgsn = None
    lac = None
    rac = None
    cellid = None
    bvci = None
    defaults_cfg_name = None

##############
# PROTECTED
##############
    def __init__(self, suite_run, conf, name, defaults_cfg_name):
        super().__init__(log.C_RUN, name)
        self.suite_run = suite_run
        self.conf = conf
        self.defaults_cfg_name = defaults_cfg_name

    def conf_for_bsc_prepare(self):
        values = config.get_defaults('bsc_bts')
        config.overlay(values, config.get_defaults(self.defaults_cfg_name))
        if self.lac is not None:
            config.overlay(values, { 'location_area_code': self.lac })
        if self.rac is not None:
            config.overlay(values, { 'routing_area_code': self.rac })
        if self.cellid is not None:
            config.overlay(values, { 'cell_identity': self.cellid })
        if self.bvci is not None:
            config.overlay(values, { 'bvci': self.bvci })
        config.overlay(values, self.conf)

        sgsn_conf = {} if self.sgsn is None else self.sgsn.conf_for_client()
        config.overlay(values, sgsn_conf)
        return values

########################
# PUBLIC - INTERNAL API
########################
    @abstractmethod
    def conf_for_bsc(self):
        'Used by bsc objects to get path to socket.'
        pass

    def remote_addr(self):
        return self.conf.get('addr')

    def cleanup(self):
        'Nothing to do by default. Subclass can override if required.'
        pass

###################
# PUBLIC (test API included)
###################
    @abstractmethod
    def start(self):
        'Starts BTS proccess and sets self.proc_bts with an object of Process interface'
        pass

    @abstractmethod
    def ready_for_pcu(self):
        'True if the BTS is prepared to have a PCU connected, false otherwise'
        pass

    @abstractmethod
    def pcu(self):
        'Get the Pcu object associated with the BTS'
        pass

    def set_bsc(self, bsc):
        self.bsc = bsc

    def set_sgsn(self, sgsn):
        self.sgsn = sgsn

    def set_lac(self, lac):
        self.lac = lac

    def set_rac(self, rac):
        self.rac = rac

    def set_cellid(self, cellid):
        self.cellid = cellid

    def set_bvci(self, bvci):
        self.bvci = bvci

# vim: expandtab tabstop=4 shiftwidth=4
