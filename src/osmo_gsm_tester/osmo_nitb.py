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

from . import log, util, config, template, process, osmo_ctrl, pcap_recorder, smsc

class OsmoNitb(log.Origin):
    suite_run = None
    ip_address = None
    run_dir = None
    config_file = None
    process = None
    bts = None
    smsc = None
    encryption = None

    def __init__(self, suite_run, ip_address):
        super().__init__(log.C_RUN, 'osmo-nitb_%s' % ip_address.get('addr'))
        self.suite_run = suite_run
        self.ip_address = ip_address
        self.bts = []
        self.smsc = smsc.Smsc((ip_address.get('addr'), 2775))

    def start(self):
        self.log('Starting osmo-nitb')
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()
        inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-nitb')))
        binary = inst.child('bin', 'osmo-nitb')
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % inst)

        iface = util.ip_to_iface(self.addr())
        pcap_recorder.PcapRecorder(self.suite_run, self.run_dir.new_dir('pcap'), iface,
                                   'host %s and port not 22' % self.addr())

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        self.process = process.Process(self.name(), self.run_dir,
                                       (binary, '-c',
                                       os.path.abspath(self.config_file)),
                                       env=env)
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def configure(self):
        self.config_file = self.run_dir.new_file('osmo-nitb.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(nitb=config.get_defaults('nitb'))
        config.overlay(values, self.suite_run.config())
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

    def subscriber_add(self, modem, msisdn=None, algo=None):
        if msisdn is None:
            msisdn = self.suite_run.resources_pool.next_msisdn(modem)
        modem.set_msisdn(msisdn)

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

    def running(self):
        return not self.process.terminated()


class OsmoNitbCtrl(log.Origin):
    PORT = 4249
    SUBSCR_MODIFY_VAR = 'subscriber-modify-v1'
    SUBSCR_MODIFY_REPLY_RE = re.compile("SET_REPLY (\d+) %s OK" % SUBSCR_MODIFY_VAR)
    SUBSCR_DELETE_VAR = 'subscriber-delete-v1'
    SUBSCR_DELETE_REPLY_RE = re.compile("SET_REPLY (\d+) %s Removed" % SUBSCR_DELETE_VAR)
    SUBSCR_LIST_ACTIVE_VAR = 'subscriber-list-active-v1'

    def __init__(self, nitb):
        self.nitb = nitb
        super().__init__(log.C_BUS, 'CTRL(%s:%d)' % (self.nitb.addr(), OsmoNitbCtrl.PORT))

    def ctrl(self):
        return osmo_ctrl.OsmoCtrl(self.nitb.addr(), OsmoNitbCtrl.PORT)

    def subscriber_add(self, imsi, msisdn, ki=None, algo=None):
        created = False

        if algo:
            value = '%s,%s,%s,%s' % (imsi,msisdn,algo,ki)
        else:
            value = '%s,%s' % (imsi, msisdn)

        with self.ctrl() as ctrl:
            ctrl.do_set(OsmoNitbCtrl.SUBSCR_MODIFY_VAR, value)
            data = ctrl.receive()
            (answer, data) = ctrl.remove_ipa_ctrl_header(data)
            answer_str = answer.decode('utf-8')
            res = OsmoNitbCtrl.SUBSCR_MODIFY_REPLY_RE.match(answer_str)
            if not res:
                raise RuntimeError('Cannot create subscriber %r (answer=%r)' % (imsi, answer_str))
            self.dbg('Created subscriber', imsi=imsi, msisdn=msisdn)

    def subscriber_delete(self, imsi):
        with self.ctrl() as ctrl:
            ctrl.do_set(OsmoNitbCtrl.SUBSCR_DELETE_VAR, imsi)
            data = ctrl.receive()
            (answer, data) = ctrl.remove_ipa_ctrl_header(data)
            answer_str = answer.decode('utf-8')
            res = OsmoNitbCtrl.SUBSCR_DELETE_REPLY_RE.match(answer_str)
            if not res:
                raise RuntimeError('Cannot delete subscriber %r (answer=%r)' % (imsi, answer_str))
            self.dbg('Deleted subscriber', imsi=imsi)

    def subscriber_list_active(self):
        aslist_str = ""
        with self.ctrl() as ctrl:
            ctrl.do_get(OsmoNitbCtrl.SUBSCR_LIST_ACTIVE_VAR)
            # This is legacy code from the old osmo-gsm-tester.
            # looks like this doesn't work for long data.
            data = ctrl.receive()
            while (len(data) > 0):
                (answer, data) = ctrl.remove_ipa_ctrl_header(data)
                answer_str = answer.decode('utf-8')
                answer_str = answer_str.replace('\n', ' ')
                aslist_str = answer_str
            return aslist_str

# vim: expandtab tabstop=4 shiftwidth=4
