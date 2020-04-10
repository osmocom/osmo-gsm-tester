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

import copy
from abc import ABCMeta, abstractmethod
from ..core import log, config, schema

class Bts(log.Origin, metaclass=ABCMeta):

##############
# PROTECTED
##############
    def __init__(self, suite_run, conf, name, defaults_cfg_name):
        super().__init__(log.C_RUN, name)
        self.bsc = None
        self.sgsn = None
        self.lac = None
        self.rac = None
        self.cellid = None
        self.bvci = None
        self._num_trx = 1
        self._max_trx = None
        self.overlay_trx_list = []
        self.suite_run = suite_run
        self.conf = conf
        self.defaults_cfg_name = defaults_cfg_name
        self._init_num_trx()

    def _resolve_bts_cfg(self, cfg_name):
        res = None
        val = config.get_defaults('bsc_bts').get(cfg_name)
        if val is not None:
            res = val
        val = config.get_defaults(self.defaults_cfg_name).get(cfg_name)
        if val is not None:
            res = val
        val = self.conf.get(cfg_name)
        if val is not None:
            res = val
        return res

    def _init_num_trx(self):
        self._num_trx = 1
        self._max_trx = None
        val = self._resolve_bts_cfg('num_trx')
        if val is not None:
            self._num_trx = int(val)
        val = self._resolve_bts_cfg('max_trx')
        if val is not None:
            self._max_trx = int(val)
        self._validate_new_num_trx(self._num_trx)
        self.overlay_trx_list = [Bts._new_default_trx_cfg() for trx in range(self._num_trx)]

    def _validate_new_num_trx(self, num_trx):
        if self._max_trx is not None and num_trx > self._max_trx:
            raise log.Error('Amount of TRX requested is too high for maximum allowed: %u > %u' %(num_trx, self._max_trx))

    @staticmethod
    def _new_default_trx_cfg():
        return {'timeslot_list':[{} for ts in range(8)]}

    @staticmethod
    def _trx_list_recreate(trx_list, new_size):
        curr_len = len(trx_list)
        if new_size < curr_len:
            trx_list = trx_list[0:new_size]
        elif new_size > curr_len:
            for i in range(new_size - curr_len):
                trx_list.append(Bts._new_default_trx_cfg())
        return trx_list

    def conf_for_bsc_prepare(self):
        values = config.get_defaults('bsc_bts')
        # Make sure the trx_list is adapted to num of trx configured at runtime
        # to avoid overlay issues.
        trx_list = values.get('trx_list')
        if trx_list and len(trx_list) != self.num_trx():
            values['trx_list'] = Bts._trx_list_recreate(trx_list, self.num_trx())

        bts_defaults = config.get_defaults(self.defaults_cfg_name)
        trx_list = bts_defaults.get('trx_list')
        if trx_list and len(trx_list) != self.num_trx():
            bts_defaults['trx_list'] = Bts._trx_list_recreate(trx_list, self.num_trx())

        config.overlay(values, bts_defaults)
        if self.lac is not None:
            config.overlay(values, { 'location_area_code': self.lac })
        if self.rac is not None:
            config.overlay(values, { 'routing_area_code': self.rac })
        if self.cellid is not None:
            config.overlay(values, { 'cell_identity': self.cellid })
        if self.bvci is not None:
            config.overlay(values, { 'bvci': self.bvci })

        conf = copy.deepcopy(self.conf)
        trx_list = conf.get('trx_list')
        if trx_list and len(trx_list) != self.num_trx():
            conf['trx_list'] = Bts._trx_list_recreate(trx_list, self.num_trx())
        config.overlay(values, conf)

        sgsn_conf = {} if self.sgsn is None else self.sgsn.conf_for_client()
        config.overlay(values, sgsn_conf)

        config.overlay(values, { 'trx_list': self.overlay_trx_list })
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

    def egprs_enabled(self):
        return self.conf_for_bsc()['gprs_mode'] == 'egprs'

    def cleanup(self):
        'Nothing to do by default. Subclass can override if required.'
        pass

###################
# PUBLIC (test API included)
###################
    @abstractmethod
    def start(self, keepalive=False):
        '''Starts BTS. If keepalive is set, it will expect internal issues and
        respawn related processes when detected'''
        pass

    @abstractmethod
    def ready_for_pcu(self):
        'True if the BTS is prepared to have a PCU connected, false otherwise'
        pass

    @abstractmethod
    def pcu(self):
        'Get the Pcu object associated with the BTS'
        pass

    def bts_type(self):
        'Get the type of BTS'
        return self.conf.get('type')

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

    def set_num_trx(self, num_trx):
        assert num_trx > 0
        self._validate_new_num_trx(num_trx)
        if num_trx == self._num_trx:
            return
        self._num_trx = num_trx
        self.overlay_trx_list = Bts._trx_list_recreate(self.overlay_trx_list, num_trx)

    def num_trx(self):
        return self._num_trx

    def set_trx_phy_channel(self, trx_idx, ts_idx, config):
        assert trx_idx < self._num_trx
        assert ts_idx < 8
        schema.phy_channel_config(config) # validation
        self.overlay_trx_list[trx_idx]['timeslot_list'][ts_idx]['phys_chan_config'] = config

# vim: expandtab tabstop=4 shiftwidth=4
