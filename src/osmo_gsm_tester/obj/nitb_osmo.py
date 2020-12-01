# osmo_gsm_tester: specifics for running an osmo-nitb
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
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
import re
import pprint

from ..core import log, util, config, template, process
from . import osmo_ctrl, pcap_recorder, smsc

class OsmoNitb(log.Origin):

    def __init__(self, testenv, ip_address):
        super().__init__(log.C_RUN, 'osmo-nitb_%s' % ip_address.get('addr'))
        self.run_dir = None
        self.config_file = None
        self.process = None
        self.encryption = None
        self.testenv = testenv
        self.ip_address = ip_address
        self.bts = []
        self.smsc = smsc.Smsc((ip_address.get('addr'), 2775))

    def start(self):
        self.log('Starting osmo-nitb')
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()
        inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('osmo-nitb')))
        binary = inst.child('bin', 'osmo-nitb')
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % inst)

        pcap_recorder.PcapRecorder(self.testenv, self.run_dir.new_dir('pcap'), None,
                                   'host %s and port not 22' % self.addr())

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        self.process = process.Process(self.name(), self.run_dir,
                                       (binary, '-c',
                                       os.path.abspath(self.config_file)),
                                       env=env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

    def configure(self):
        self.config_file = self.run_dir.new_file('osmo-nitb.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(nitb=config.get_defaults('nitb'))
        config.overlay(values, self.testenv.suite().config())
        config.overlay(values, dict(nitb=dict(ip_address=self.ip_address)))

        bts_list = []
        for bts in self.bts:
            bts_list.append(bts.conf_for_bsc())
        config.overlay(values, dict(nitb=dict(net=dict(bts_list=bts_list))))
        config.overlay(values, self.smsc.get_config())

        # runtime parameters:
        if self.encryption is not None:
            encryption_vty = util.encryption2osmovty(self.encryption)
        else:
            encryption_vty = util.encryption2osmovty(values['nitb']['net']['encryption'])
        config.overlay(values, dict(nitb=dict(net=dict(encryption=encryption_vty))))

        self.config = values

        self.dbg('NITB CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-nitb.cfg', values)
            self.dbg(r)
            f.write(r)

    def addr(self):
        return self.ip_address.get('addr')

    def bts_add(self, bts):
        self.bts.append(bts)
        bts.set_bsc(self)

    def set_encryption(self, val):
        self.encryption = val

    def mcc(self):
        return self.config['nitb']['net']['mcc']

    def mnc(self):
        return self.config['nitb']['net']['mnc']

    def mcc_mnc(self):
        return (self.mcc(), self.mnc())

    def bts_num(self, bts):
        'Provide number id used by OsmoNITB to identify configured BTS'
        # We take advantage from the fact that VTY code assigns VTY in ascending
        # order through the bts nodes found. As we populate the config iterating
        # over this list, we have a 1:1 match in indexes.
        return self.bts.index(bts)

    def subscriber_add(self, modem, msisdn=None, algo=None):
        if msisdn is None:
            msisdn = modem.msisdn()

        if not algo:
            alg_str = modem.auth_algo()
            if not alg_str or alg_str == 'none':
                algo = None
            elif alg_str == 'comp128v1':
                algo = 'comp128v1'
            elif alg_str == 'xor':
                algo = 'xor'
        if algo is not None and not modem.ki():
            raise log.Error("Auth algo %r selected and no KI specified" % algo)

        self.log('Add subscriber', msisdn=msisdn, imsi=modem.imsi())
        OsmoNitbCtrl(self).subscriber_add(modem.imsi(), msisdn, modem.ki(), algo)

    def subscriber_delete(self, modem):
        self.log('Delete subscriber', imsi=modem.imsi())
        OsmoNitbCtrl(self).subscriber_delete(modem.imsi())

    def subscriber_attached(self, *modems):
        return self.imsi_attached(*[m.imsi() for m in modems])

    def imsi_attached(self, *imsis):
        attached = self.imsi_list_attached()
        self.dbg('attached:', attached)
        return all([(imsi in attached) for imsi in imsis])

    def imsi_list_attached(self):
        return OsmoNitbCtrl(self).subscriber_list_active()

    def bts_is_connected(self, bts):
        return OsmoNitbCtrl(self).bts_is_connected(self.bts_num(bts))

    def running(self):
        return not self.process.terminated()


class OsmoNitbCtrl(osmo_ctrl.OsmoCtrl):
    def __init__(self, nitb, port=4249):
        self.nitb = nitb
        super().__init__(nitb.addr(), port)

    def subscriber_add(self, imsi, msisdn, ki=None, algo=None):
        if algo:
            value = '%s,%s,%s,%s' % (imsi,msisdn,algo,ki)
        else:
            value = '%s,%s' % (imsi, msisdn)

        assert self.set_var('subscriber-modify-v1', value) == 'OK'
        self.dbg('Created subscriber', imsi=imsi, msisdn=msisdn)

    def subscriber_delete(self, imsi):
        assert self.set_var('subscriber-delete-v1', imsi) == 'Removed'
        self.dbg('Deleted subscriber', imsi=imsi)

    def subscriber_list_active(self):
        return self.get_var('subscriber-list-active-v1').replace('\n', ' ')

    def bts_is_connected(self, bts_num):
        return self.get_var('bts.%d.oml-connection-state' % bts_num) == 'connected'

# vim: expandtab tabstop=4 shiftwidth=4
