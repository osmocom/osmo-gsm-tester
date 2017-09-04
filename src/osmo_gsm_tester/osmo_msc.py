# osmo_gsm_tester: specifics for running an osmo-msc
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
import pprint

from . import log, util, config, template, process, osmo_ctrl, pcap_recorder, smsc

class OsmoMsc(log.Origin):
    suite_run = None
    ip_address = None
    run_dir = None
    config_file = None
    process = None
    hlr = None
    config = None
    smsc = None
    encryption = None
    authentication = None

    def __init__(self, suite_run, hlr, mgcpgw, ip_address):
        super().__init__(log.C_RUN, 'osmo-msc_%s' % ip_address.get('addr'))
        self.suite_run = suite_run
        self.ip_address = ip_address
        self.hlr = hlr
        self.mgcpgw = mgcpgw
        self.smsc = smsc.Smsc((ip_address.get('addr'), 2775))

    def start(self):
        self.log('Starting osmo-msc')
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()
        inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-msc')))
        binary = inst.child('bin', 'osmo-msc')
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
        self.config_file = self.run_dir.new_file('osmo-msc.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(msc=config.get_defaults('msc'))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, dict(msc=dict(ip_address=self.ip_address)))
        config.overlay(values, self.mgcpgw.conf_for_msc())
        config.overlay(values, self.hlr.conf_for_msc())
        config.overlay(values, self.smsc.get_config())

        # runtime parameters:
        if self.encryption is not None:
            encryption_vty = util.encryption2osmovty(self.encryption)
        else:
            encryption_vty = util.encryption2osmovty(values['msc']['net']['encryption'])
        config.overlay(values, dict(msc=dict(net=dict(encryption=encryption_vty))))
        if self.authentication is not None:
            config.overlay(values, dict(msc=dict(net=dict(authentication=self.authentication))))


        self.config = values

        self.dbg('MSC CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-msc.cfg', values)
            self.dbg(r)
            f.write(r)

    def addr(self):
        return self.ip_address.get('addr')

    def set_encryption(self, val):
        self.encryption = val

    def set_authentication(self, val):
        if val is None:
            self.authroziation = None
            return
        self.authentication = "required" if val else "optional"

    def mcc(self):
        return self.config['msc']['net']['mcc']

    def mnc(self):
        return self.config['msc']['net']['mnc']

    def mcc_mnc(self):
        return (self.mcc(), self.mnc())

    def subscriber_attached(self, *modems):
        return self.imsi_attached(*[m.imsi() for m in modems])

    def imsi_attached(self, *imsis):
        attached = self.imsi_list_attached()
        log.dbg('attached:', attached)
        return all([(imsi in attached) for imsi in imsis])

    def imsi_list_attached(self):
        return OsmoMscCtrl(self).subscriber_list_active()

    def running(self):
        return not self.process.terminated()


class OsmoMscCtrl(log.Origin):
    PORT = 4255
    SUBSCR_LIST_ACTIVE_VAR = 'subscriber-list-active-v1'

    def __init__(self, msc):
        self.msc = msc
        super().__init__(log.C_BUS, 'CTRL(%s:%d)' % (self.msc.addr(), self.PORT))

    def ctrl(self):
        return osmo_ctrl.OsmoCtrl(self.msc.addr(), self.PORT)

    def subscriber_list_active(self):
        aslist_str = ""
        with self.ctrl() as ctrl:
            ctrl.do_get(self.SUBSCR_LIST_ACTIVE_VAR)
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
