# osmo_gsm_tester: base classes to share code among BTS subclasses.
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
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
from . import log, config, util, template, process, bts, pcu_osmo

class OsmoBts(bts.Bts, metaclass=ABCMeta):

##############
# PROTECTED
##############
    def __init__(self, suite_run, conf, name, defaults_cfg_name):
        super().__init__(suite_run, conf, name, defaults_cfg_name)
        self._pcu = None
        self.proc_bts = None
        if len(self.pcu_socket_path().encode()) > 107:
            raise log.Error('Path for pcu socket is longer than max allowed len for unix socket path (107):', self.pcu_socket_path())

########################
# PUBLIC - INTERNAL API
########################
    @abstractmethod
    def conf_for_bsc(self):
        # coming from bts.Bts, we forward the implementation to children.
        pass

    @abstractmethod
    def pcu_socket_path(self):
        'Used by pcu objects to get path to socket.'
        pass

    @abstractmethod
    def create_pcu(self):
        'Used by base class. Subclass can create different pcu implementations.'
        pass

###################
# PUBLIC (test API included)
###################
    @abstractmethod
    def start(self, keepalive=False):
        # coming from bts.Bts, we forward the implementation to children.
        pass

    @abstractmethod
    def ready_for_pcu(self):
        'Used by tests to know when BTS is prepared and PCU can be started.'
        pass

    def pcu(self):
        if self._pcu is None:
            self._pcu = self.create_pcu()
        return self._pcu

class OsmoBtsMainUnit(OsmoBts, metaclass=ABCMeta):
##############
# PROTECTED
##############

    def __init__(self, suite_run, conf, name, defaults_cfg_name):
        self.pcu_sk_tmp_dir = None
        super().__init__(suite_run, conf, name, defaults_cfg_name)

########################
# PUBLIC - INTERNAL API
########################
    @abstractmethod
    def conf_for_bsc(self):
        # coming from bts.Bts, we forward the implementation to children.
        pass

    def cleanup(self):
        if self.pcu_sk_tmp_dir:
            try:
                os.remove(self.pcu_socket_path())
            except OSError:
                pass
            os.rmdir(self.pcu_sk_tmp_dir)

    def create_pcu(self):
        return pcu_osmo.OsmoPcu(self.suite_run, self, self.conf)

    def pcu_socket_path(self):
        if self.pcu_sk_tmp_dir is None:
            self.pcu_sk_tmp_dir = tempfile.mkdtemp('', 'ogtpcusk')
        return os.path.join(self.pcu_sk_tmp_dir, 'pcu_bts')

###################
# PUBLIC (test API included)
###################
    def ready_for_pcu(self):
        if not self.proc_bts or not self.proc_bts.is_running:
            return False
        return os.path.exists(self.pcu_socket_path())

    @abstractmethod
    def start(self, keepalive=False):
        # coming from bts.Bts, we forward the implementation to children.
        pass
