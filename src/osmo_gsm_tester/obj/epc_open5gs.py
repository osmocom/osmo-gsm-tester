# osmo_gsm_tester: specifics for running an Open5GS EPC
#
# Copyright (C) 2021 by sysmocom - s.f.m.c. GmbH
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
import copy

from ..core import log, util, config, template, process, remote
from ..core import schema
from . import epc
from .pcrf_open5gs import Open5gsPCRF
from .upf_open5gs import Open5gsUPF
from .smf_open5gs import Open5gsSMF
from .hss_open5gs import Open5gsHSS
from .mme_open5gs import Open5gsMME
from .sgwc_open5gs import Open5gsSGWC
from .sgwu_open5gs import Open5gsSGWU

def on_register_schemas():
    config_schema = {
        'db_host': schema.STR,
        }
    schema.register_config_schema('epc', config_schema)

class Open5gsEPC(epc.EPC):
##############
# PROTECTED
##############
    REMOTE_DIR = '/osmo-gsm-tester-open5gs'

    def __init__(self, testenv, run_node):
        super().__init__(testenv, run_node, 'open5gs')
        self.run_dir = None
        self.pcrf = None
        self.upf = None
        self.smf = None
        self.mme = None
        self.hss = None
        self.sgwc = None
        self.sgwu = None
        self.subscriber_list = []

    def configure(self):
        values = super().configure(['open5gs'])
        db_host = values['epc']['db_host']
        db_uri = 'mongodb://'+db_host+'/open5gs'
        config.overlay(values, dict(epc=dict(db_uri=db_uri,
                                             tun_addr=self.tun_addr(),
                                             addr_smf=self.priv_addr_smf(),
                                             addr_upf=self.priv_addr_upf(),
                                             addr_sgwc=self.priv_addr_sgwc(),
                                             addr_sgwu=self.priv_addr_sgwu(),
                                             )))
        self.fill_subscribers_mongodb(values['epc']['db_host'], 27017)
        self.pcrf = Open5gsPCRF(self.testenv, self)
        self.upf = Open5gsUPF(self.testenv, self)
        self.smf = Open5gsSMF(self.testenv, self)
        self.hss = Open5gsHSS(self.testenv, self)
        self.mme = Open5gsMME(self.testenv, self)
        self.sgwc = Open5gsSGWC(self.testenv, self)
        self.sgwu = Open5gsSGWU(self.testenv, self)
        self.pcrf.configure(copy.deepcopy(values))
        self.upf.configure(copy.deepcopy(values))
        self.smf.configure(copy.deepcopy(values))
        self.hss.configure(copy.deepcopy(values))
        self.mme.configure(copy.deepcopy(values))
        self.sgwc.configure(copy.deepcopy(values))
        self.sgwu.configure(copy.deepcopy(values))

    def gen_priv_addr(self, suffix):
        if ':' in self.addr():
            raise log.Error('IPv6 not implemented!')
        public_suffix = self.addr()[self.addr().rindex('.')+1:]
        return '127.0.' + public_suffix + '.' + str(suffix)

########################
# PUBLIC - INTERNAL API
########################

    def cleanup(self):
        if self.pcrf:
            self.pcrf.cleanup()
        if self.upf:
            self.upf.cleanup()
        if self.smf:
            self.smf.cleanup()
        if self.hss:
            self.hss.cleanup()
        if self.mme:
            self.mme.cleanup()
        if self.sgwc:
            self.sgwc.cleanup()
        if self.sgwu:
            self.sgwu.cleanup()

    def priv_addr_smf(self):
        return self.gen_priv_addr(1)

    def priv_addr_upf(self):
        return self.gen_priv_addr(2)

    def priv_addr_sgwc(self):
        return self.gen_priv_addr(3)

    def priv_addr_sgwu(self):
        return self.gen_priv_addr(4)

###################
# PUBLIC (test API included)
###################
    def start(self):
        self.log('Starting open5gs')
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()
        self.pcrf.start()
        self.upf.start()
        self.smf.start()
        self.hss.start()
        self.mme.start()
        self.sgwc.start()
        self.sgwu.start()

    def subscriber_add(self, modem, msisdn=None, algo_str=None):
        if msisdn is None:
            msisdn = modem.msisdn()

        if algo_str is None:
            algo_str = modem.auth_algo() or 'milenage'

        if algo_str == 'milenage':
            if not modem.ki():
                raise log.Error("Auth algo milenage selected but no KI specified")
            if not modem.opc():
                raise log.Error("Auth algo milenage selected but no OPC specified")
        else:
            raise log.Error("Open5Gs only supports auth algo: milenage")

        subscriber_id = len(self.subscriber_list) # list index
        self.subscriber_list.append({'id': subscriber_id, 'imsi': modem.imsi(), 'msisdn': msisdn, 'auth_algo': algo_str, 'ki': modem.ki(), 'opc': modem.opc(), 'apn_ipaddr': modem.apn_ipaddr()})
        return subscriber_id

    def fill_subscribers_mongodb(self, server, port):
        import pymongo

        myclient = pymongo.MongoClient("mongodb://" + str(server) + ":" + str(port) + "/")
        mydb = myclient["open5gs"]
        mycol = mydb["subscribers"]

        for s in self.subscriber_list:
            self.log('Insert subscriber to DB', msisdn=s['msisdn'], imsi=s['imsi'], subscriber_id=s['id'],
                     algo_str=s['auth_algo'])
            slice_data = [ { \
                "sst": 1, \
                "default_indicator": True, \
                "session": [ \
                    { \
                    "name": "internet", \
                    "type": 3, "pcc_rule": [], "ambr": {"uplink": {"value": 1, "unit": 0}, "downlink": {"value": 1, "unit": 0}}, \
                    "qos": { "index": 9, "arp": {"priority_level": 8, "pre_emption_capability": 1, "pre_emption_vulnerability": 1} } \
                    } \
                ] \
            } ]

            sub_data = {'imsi':  s['imsi'], \
                        'subscribed_rau_tau_timer': 12, \
                        'network_access_mode': 2, \
                        'subscriber_status': 0, \
                        "access_restriction_data": 32, \
                        'slice': slice_data, \
                        'ambr': {"uplink": {"value": 1, "unit": 0}, "downlink": {"value": 1, "unit": 0}}, \
                        'security': {'k': s['ki'], 'amf': '8000', 'op': None, 'opc': s['opc']},
                        'schema_version': 1, \
                        '__v': 0}
            x = mycol.insert_one(sub_data)
            self.dbg("Added subscriber with Inserted ID : " + str(x.inserted_id))
            s['inserted_id'] = x.inserted_id

    def enb_is_connected(self, enb):
        # Match against sample mmed line: "eNB-S1 accepted[172.18.50.101]:50867"
        if not self.mme or not self.mme.running():
            return False
        stdout_lines = (self.mme.process.get_stdout() or '').splitlines()
        for l in stdout_lines:
            if 'eNB' in l and 'accepted' in l and enb.addr() in l:
                return True
        return False

    def running(self):
        return self.pcrf and self.upf and self.smf and self.hss and \
               self.mme and self.sgwc and self.sgwu and \
               self.pcrf.running() and self.upf.running() and self.smf.running() and \
               self.hss.running() and self.mme.running() and self.sgwc.running() and \
               self.sgwu.running()

    def tun_addr(self):
        return '172.16.0.1'

    def get_kpis(self):
        return {}

# vim: expandtab tabstop=4 shiftwidth=4
