# osmo_gsm_tester: specifics for setting an APN on an AndroidUE modem
#
# Copyright (C) 2020 by Software Radio Systems Limited
#
# Author: Nils Fürste <nils.fuerste@softwareradiosystems.com>
# Author: Bedran Karakoc <bedran.karakoc@softwareradiosystems.com>
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

import re

from ..core import log
from ..core import schema
from .android_host import AndroidHost


class AndroidApn(AndroidHost):
##############
# PROTECTED
##############
    def __init__(self, apn, mcc, mnc, select=None):
        self.logger_name = 'apn_worker_'
        super().__init__(self.logger_name)
        self._apn_name = apn
        self._apn = apn
        self._mcc = mcc
        self._mnc = mnc
        self._select = select
        if not self._apn:
            raise log.Error('APN name not set')
        if not self._mcc:
            raise log.Error('MCC not set')
        if not self._mnc:
            raise log.Error('MNC not set')

        # optional parameters, set with set_additional_params()
        self.proxy = None
        self.port = None
        self.user = None
        self.password = None
        self.server = None
        self.mmsc = None
        self.mmsport = None
        self.mmsproxy = None
        self.auth = None
        self.type = None
        self.protocol = None
        self.mvnoval = None
        self.mvnotype = None

    def get_carrier_id(self, carrier_name):
        qry_carrier_cmd = "content query --uri \"content://telephony/carriers\""
        proc = self.run_androidue_cmd('get-carrier-id', [qry_carrier_cmd])
        proc.launch_sync()
        available_carriers = proc.get_stdout().split('\n')
        carr_id = -1
        for carr in available_carriers:
            if 'name=' + carrier_name in carr:  # found carrier
                carr_id = re.findall(r'_id=(\S+),', carr)[0]
                break
        return carr_id

    def set_new_carrier(self, apn_parameter, carr_id):
        # check if carrier was found, delete it if exists
        if carr_id != -1:
            self.delete_apn(apn_parameter['carrier'])

        set_carrier_cmd = "content insert --uri content://telephony/carriers" \
                          + " --bind name:s:\"" + apn_parameter["carrier"] + "\"" \
                          + " --bind numeric:s:\"" + apn_parameter["mcc"] + apn_parameter["mnc"] + "\"" \
                          + " --bind mcc:s:\"" + apn_parameter["mcc"] + "\"" \
                          + " --bind mnc:s:\"" + apn_parameter["mnc"] + "\""\
                          + " --bind apn:s:\"" + apn_parameter["apn"] + "\"" \
                          + " --bind user:s:\"" + apn_parameter["user"] + "\"" \
                          + " --bind password:s:\"" + apn_parameter["password"] + "\"" \
                          + " --bind mmsc:s:\"" + apn_parameter["mmsc"] + "\"" \
                          + " --bind mmsport:s:\"" + apn_parameter["mmsport"] + "\"" \
                          + " --bind mmsproxy:s:\"" + apn_parameter["mmsproxy"] + "\"" \
                          + " --bind authtype:s:\"" + apn_parameter["auth"] + "\"" \
                          + " --bind type:s:\"" + apn_parameter["type"] + "\"" \
                          + " --bind protocol:s:\"" + apn_parameter["protocol"] + "\"" \
                          + " --bind mvno_type:s:\"" + apn_parameter["mvnotype"] + "\"" \
                          + " --bind mvno_match_data:s:\"" + apn_parameter["mvnoval"] + "\""
        proc = self.run_androidue_cmd("set-new-carrier", [set_carrier_cmd])
        proc.launch_sync()
        return self.get_carrier_id(apn_parameter['carrier'])

    def set_preferred_apn(self, carr_id):
        if carr_id != -1:
            set_apn_cmd = "content insert --uri content://telephony/carriers/preferapn --bind apn_id:s:\"" + str(carr_id) + "\""
            proc = self.run_androidue_cmd('set-preferred-apn', [set_apn_cmd])
            proc.launch_sync()

    def select_apn(self, carr_name):
        carr_id = self.get_carrier_id(carr_name)
        if carr_id == 0:
            return False

        # select carrier by ID
        sel_apn_cmd = "content update --uri content://telephony/carriers/preferapn --bind apn_id:s:\"" + str(carr_id) + "\""
        proc = self.run_androidue_cmd('select-apn', [sel_apn_cmd])
        proc.launch_sync()
        return True

    def delete_apn(self, carr_name):
        set_apn_cmd = "content delete --uri content://telephony/carriers --where \'name=\"" + str(carr_name) + "\" \'"
        proc = self.run_androidue_cmd('delete-apn', [set_apn_cmd])
        proc.launch_sync()

########################
# PUBLIC - INTERNAL API
########################
    @classmethod
    def from_conf(cls, conf):
        return cls(conf.get('apn', None), conf.get('mcc', None),
                   conf.get('mnc', None), conf.get('select', None))

    @classmethod
    def schema(cls):
        resource_schema = {
            'apn': schema.STR,
            'mcc': schema.STR,
            'mnc': schema.STR,
            'select': schema.BOOL_STR,
            }
        return resource_schema

    def configure(self, testenv, run_dir, run_node, rem_host):
        self.testenv = testenv
        self.rem_host = rem_host
        self._run_node = run_node
        self.run_dir = run_dir
        self.logger_name += self._run_node.run_addr()
        self.set_name(self.logger_name)

    def set_additional_params(self, proxy=None, port=None, user=None, password=None, server=None, auth=None, apn_type=None,
                              mmsc=None, mmsport=None, mmsproxy=None,  protocol=None, mvnoval=None, mvnotype=None):
        self.proxy = proxy
        self.port = port
        self.user = user
        self.password = password
        self.server = server
        self.auth = auth
        self.type = apn_type
        self.mmsc = mmsc
        self.mmsport = mmsport
        self.mmsproxy = mmsproxy
        self.protocol = protocol
        self.mvnoval = mvnoval
        self.mvnotype = mvnotype

    def set_apn(self):
        apn_params = {
            'carrier': self._apn_name,
            'apn': self._apn,
            'proxy': self.proxy or '',
            'port': self.port or '',
            'user': self.user or '',
            'password': self.password or '',
            'server': self.server or '',
            'mmsc': self.mmsc or '',
            'mmsport': self.mmsport or '',
            'mmsproxy': self.mmsproxy or '',
            'mcc': self._mcc,
            'mnc': self._mnc,
            'auth': self.auth or '-1',
            'type': self.type or 'default',
            'protocol': self.protocol or '',
            'mvnotype': self.mvnotype or '',
            'mvnoval': self.mvnoval or '',
        }
        self.dbg('APN parameters: ' + str(apn_params))

        # search for carrier in database
        carrier_id = self.get_carrier_id(apn_params['carrier'])

        # add/update carrier
        carrier_id = self.set_new_carrier(apn_params, carrier_id)

        # select as preferred APN
        if self.select:
            self.set_preferred_apn(carrier_id)

    def __str__(self):
        return self.name()

    def apn(self):
        return self._apn

    def mcc(self):
        return self._mcc

    def mnc(self):
        return self._mnc

    def select(self):
        return self._select

# vim: expandtab tabstop=4 shiftwidth=4
