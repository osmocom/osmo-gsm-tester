# osmo_gsm_tester: specifics for running an osmo-bsc
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

from . import log, util, config, template, process, osmo_ctrl, pcap_recorder

class OsmoBsc(log.Origin):

    def __init__(self, suite_run, msc, mgw, stp, ip_address):
        super().__init__(log.C_RUN, 'osmo-bsc_%s' % ip_address.get('addr'))
        self.run_dir = None
        self.config_file = None
        self.process = None
        self.encryption = None
        self.rsl_ip = None
        self.suite_run = suite_run
        self.ip_address = ip_address
        self.bts = []
        self.msc = msc
        self.mgw = mgw
        self.stp = stp

    def start(self):
        self.log('Starting osmo-bsc')
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-bsc')))

        binary = inst.child('bin', 'osmo-bsc')
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % inst)

        if self.rsl_ip and self.addr() != self.rsl_ip:
            filter = 'host %s or host %s and port not 22' % (self.addr(), self.rsl_ip)
        else:
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
        self.config_file = self.run_dir.new_file('osmo-bsc.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(bsc=config.get_defaults('bsc'))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, dict(bsc=dict(ip_address=self.ip_address)))
        config.overlay(values, self.mgw.conf_for_client())
        config.overlay(values, self.stp.conf_for_client())

        bts_list = []
        for bts in self.bts:
            bts_list.append(bts.conf_for_bsc())
        config.overlay(values, dict(bsc=dict(net=dict(bts_list=bts_list))))

        # runtime parameters:
        if self.encryption is not None:
            encryption_vty = util.encryption2osmovty(self.encryption)
        else:
            encryption_vty = util.encryption2osmovty(values['bsc']['net']['encryption'])
        config.overlay(values, dict(bsc=dict(net=dict(encryption=encryption_vty))))

        if self.rsl_ip is not None:
            config.overlay(values, dict(bsc=dict(net=dict(rsl_ip=self.rsl_ip))))

        self.dbg('BSC CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-bsc.cfg', values)
            self.dbg(r)
            f.write(r)

    def addr(self):
        return self.ip_address.get('addr')

    def set_encryption(self, val):
        self.encryption = val

    def set_rsl_ip(self, ip_addr):
        '''Overwrite RSL IPaddr option sent to all BTS during OML config. Useful
        for tests only willing to use osmo-bsc to do the OML setup but using
        other external entities to test the RSL path, such as TTCN3 tests.'''
        self.rsl_ip = ip_addr

    def bts_add(self, bts):
        self.bts.append(bts)
        bts.set_bsc(self)

    def bts_num(self, bts):
        'Provide number id used by OsmoNITB to identify configured BTS'
        # We take advantage from the fact that VTY code assigns VTY in ascending
        # order through the bts nodes found. As we populate the config iterating
        # over this list, we have a 1:1 match in indexes.
        return self.bts.index(bts)

    def bts_is_connected(self, bts):
        return OsmoBscCtrl(self).bts_is_connected(self.bts_num(bts))

    def running(self):
        return not self.process.terminated()


class OsmoBscCtrl(log.Origin):
    PORT = 4249
    BTS_OML_STATE_VAR = "bts.%d.oml-connection-state"
    BTS_OML_STATE_RE = re.compile("GET_REPLY (\d+) bts.\d+.oml-connection-state (?P<oml_state>\w+)")

    def __init__(self, bsc):
        self.bsc = bsc
        super().__init__(log.C_BUS, 'CTRL(%s:%d)' % (self.bsc.addr(), OsmoBscCtrl.PORT))

    def ctrl(self):
        return osmo_ctrl.OsmoCtrl(self.bsc.addr(), OsmoBscCtrl.PORT)

    def bts_is_connected(self, bts_num):
        with self.ctrl() as ctrl:
            ctrl.do_get(OsmoBscCtrl.BTS_OML_STATE_VAR % bts_num)
            data = ctrl.receive()
            while (len(data) > 0):
                (answer, data) = ctrl.remove_ipa_ctrl_header(data)
                answer_str = answer.decode('utf-8')
                answer_str = answer_str.replace('\n', ' ')
                res = OsmoBscCtrl.BTS_OML_STATE_RE.match(answer_str)
                if res:
                    oml_state = str(res.group('oml_state'))
                    if oml_state == 'connected':
                        return True
        return False

# vim: expandtab tabstop=4 shiftwidth=4
