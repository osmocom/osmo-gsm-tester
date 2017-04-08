# osmo_gsm_tester: specifics for running an osmo-nitb
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import random
import re
import socket

from . import log, util, config, template, process, osmo_ctrl

class OsmoNitb(log.Origin):
    suite_run = None
    nitb_iface = None
    run_dir = None
    config_file = None
    process = None
    bts = None

    def __init__(self, suite_run, nitb_iface):
        self.suite_run = suite_run
        self.nitb_iface = nitb_iface
        self.set_log_category(log.C_RUN)
        self.set_name('osmo-nitb_%s' % nitb_iface.get('addr'))
        self.bts = []

    def start(self):
        self.log('Starting osmo-nitb')
        self.run_dir = util.Dir(self.suite_run.trial.get_run_dir().new_dir(self.name()))
        self.configure()
        inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-nitb')))
        binary = inst.child('bin', 'osmo-nitb')
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % inst)
        env = { 'LD_LIBRARY_PATH': lib }
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
        config.overlay(values, dict(nitb_iface=self.nitb_iface))

        bts_list = []
        for bts in self.bts:
            bts_list.append(bts.conf_for_nitb())
        config.overlay(values, dict(nitb=dict(net=dict(bts_list=bts_list))))

        self.dbg(conf=values)

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-nitb.cfg', values)
            self.dbg(r)
            f.write(r)

    def addr(self):
        return self.nitb_iface.get('addr')

    def add_bts(self, bts):
        self.bts.append(bts)
        bts.set_nitb(self)

    def add_subscriber(self, modem, msisdn=None):
        if msisdn is None:
            msisdn = self.suite_run.resources_pool.next_msisdn(modem)
        modem.set_msisdn(msisdn)
        self.log('Add subscriber', msisdn=msisdn, imsi=modem.imsi())
        with self:
            OsmoNitbCtrl(self).add_subscriber(modem.imsi(), msisdn, modem.ki())

    def subscriber_attached(self, *modems):
        return all([self.imsi_attached(m.imsi()) for m in modems])

    def imsi_attached(self, imsi):
        return random.choice((True, False))

    def sms_received(self, sms):
        return random.choice((True, False))

    def running(self):
        return not self.process.terminated()


class OsmoNitbCtrl(log.Origin):
    PORT = 4249
    SUBSCR_MODIFY_VAR = 'subscriber-modify-v1'
    SUBSCR_MODIFY_REPLY_RE = re.compile("SET_REPLY (\d+) %s OK" % SUBSCR_MODIFY_VAR)
    SUBSCR_LIST_ACTIVE_VAR = 'subscriber-list-active-v1'

    def __init__(self, nitb):
        self.nitb = nitb
        self.set_name('CTRL(%s:%d)' % (self.nitb.addr(), OsmoNitbCtrl.PORT))
        self.set_child_of(nitb)

    def ctrl(self):
        return osmo_ctrl.OsmoCtrl(self.nitb.addr(), OsmoNitbCtrl.PORT)

    def add_subscriber(self, imsi, msisdn, ki=None, algo=None):
        created = False
        if ki and not algo:
            algo = 'comp128v1'

        if algo:
            value = '%s,%s,%s,%s' % (imsi,msisdn,algo,ki)
        else:
            value = '%s,%s' % (imsi, msisdn)

        with osmo_ctrl.OsmoCtrl(self.nitb.addr(), OsmoNitbCtrl.PORT) as ctrl:
            ctrl.do_set(OsmoNitbCtrl.SUBSCR_MODIFY_VAR, value)
            data = ctrl.receive()
            (answer, data) = ctrl.remove_ipa_ctrl_header(data)
            answer_str = answer.decode('utf-8')
            res = OsmoNitbCtrl.SUBSCR_MODIFY_REPLY_RE.match(answer_str)
            if not res:
                raise RuntimeError('Cannot create subscriber %r (answer=%r)' % (imsi, answer_str))
            self.dbg('Created subscriber', imsi=imsi, msisdn=msisdn)
            return True

    def subscriber_list_active(self):
        var = 'subscriber-list-active-v1'
        aslist_str = ""
        with osmo_ctrl.OsmoCtrl(self.nitb.addr(), OsmoNitbCtrl.PORT) as ctrl:
            self.ctrl.do_get(OsmoNitbCtrl.SUBSCR_LIST_ACTIVE_VAR)
            # this looks like it doesn't work for long data. It's legacy code from the old osmo-gsm-tester.
            data = self.ctrl.receive()
            while (len(data) > 0):
                (answer, data) = self.ctrl.remove_ipa_ctrl_header(data)
                answer = answer.replace('\n', ' ')
                aslist_str = answer
            return aslist_str

# vim: expandtab tabstop=4 shiftwidth=4
