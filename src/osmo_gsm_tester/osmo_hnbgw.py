# osmo_gsm_tester: specifics for running an osmo-hnbgw
#
# Copyright (C) 2019 by sysmocom - s.f.m.c. GmbH
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
import re
import pprint

from . import log, util, config, template, process, osmo_ctrl, pcap_recorder

class OsmoHnbgw(log.Origin):

    def __init__(self, suite_run, stp, ip_address):
        super().__init__(log.C_RUN, 'osmo-hnbgw_%s' % ip_address.get('addr'))
        self.run_dir = None
        self.config_file = None
        self.process = None
        self.suite_run = suite_run
        self.ip_address = ip_address
        self.hnb_li = []
        self.stp = stp

    def start(self):
        self.log('Starting osmo-hnbgw')
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-iuh')))

        binary = inst.child('bin', 'osmo-hnbgw')
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % inst)


        filter = 'host %s and port not 22' % self.addr()
        pcap_recorder.PcapRecorder(self.suite_run, self.run_dir.new_dir('pcap'), None, filter)

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        self.process = process.Process(self.name(), self.run_dir,
                                       (binary, '-c',
                                        os.path.abspath(self.config_file)),
                                       env=env)
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def configure(self):
        self.config_file = self.run_dir.new_file('osmo-hnbgw.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(hnbgw=config.get_defaults('hnbgw'))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, dict(hnbgw=dict(ip_address=self.ip_address)))
        config.overlay(values, self.stp.conf_for_client())

        #hnb_list = []
        #for hnb in self.hnb_li:
        #    hnb_list.append(hnb.conf_for_hnbgw())
        #config.overlay(values, dict(hnbgw=dict(hnb_list=hnb_list)))

        self.dbg('HNBGW CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-hnbgw.cfg', values)
            self.dbg(r)
            f.write(r)

    def addr(self):
        return self.ip_address.get('addr')

    def hnb_add(self, hnb):
        self.hnb_li.append(hnb)
        hnb.set_hnbgw(self)

    def hnb_num(self, hnb):
        'Provide number id used by OsmoHNBGW to identify configured HNB'
        # We take advantage from the fact that VTY code assigns VTY in ascending
        # order through the HNB nodes found. As we populate the config iterating
        # over this list, we have a 1:1 match in indexes.
        return self.hnb_li.index(hnb)

    def hnb_is_connected(self, hnb):
        return OsmoHnbgwCtrl(self).hnb_is_connected(self.hnb_num(hnb))

    def running(self):
        return not self.process.terminated()


class OsmoHnbgwCtrl(log.Origin):
    PORT = 4261
    HNB_INFO_VAR = "hnb.%d.info"
    HNB_INFO_RE = re.compile("GET_REPLY (\d+) hnb.\d+.info (?P<info>\w+)")

    def __init__(self, hnbgw):
        self.hnbgw = hnbgw
        super().__init__(log.C_BUS, 'CTRL(%s:%d)' % (self.hnbgw.addr(), OsmoHnbgwCtrl.PORT))

    def ctrl(self):
        return osmo_ctrl.OsmoCtrl(self.hnbgw.addr(), OsmoHnbgwCtrl.PORT)

    def hnb_is_connected(self, hnb_num):
        with self.ctrl() as ctrl:
            ctrl.do_get(OsmoHnbgwCtrl.HNB_INFO_VAR % hnb_num)
            data = ctrl.receive()
            while (len(data) > 0):
                (answer, data) = ctrl.remove_ipa_ctrl_header(data)
                answer_str = answer.decode('utf-8')
                answer_str = answer_str.replace('\n', ' ')
                res = OsmoHnbgwCtrl.HNB_INFO_RE.match(answer_str)
                if res:
                    info = str(res.group('info'))
                    self.log('got info: "%s"' % info)
                    if info == 'connected':
                        return True
        return False

# vim: expandtab tabstop=4 shiftwidth=4
