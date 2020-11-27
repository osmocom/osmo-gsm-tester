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
import re

from ..core import log, util, config, template, process
from ..core import schema
from . import osmo_ctrl, osmo_vty, pcap_recorder

def on_register_schemas():
    config_schema = {
        'net.codec_list[]': schema.CODEC,
        }
    schema.register_config_schema('bsc', config_schema)


class OsmoBsc(log.Origin):

    def __init__(self, testenv, msc, mgw, stp, ip_address):
        super().__init__(log.C_RUN, 'osmo-bsc_%s' % ip_address.get('addr'))
        self.run_dir = None
        self.config_file = None
        self.process = None
        self.encryption = None
        self.rsl_ip = None
        self.use_osmux = "off"
        self.testenv = testenv
        self.ip_address = ip_address
        self.bts = []
        self.msc = msc
        self.mgw = mgw
        self.stp = stp
        self.vty = None

    def start(self):
        self.log('Starting osmo-bsc')
        self.run_dir = util.Dir(self.testenv.test().get_run_dir().new_dir(self.name()))
        self.configure()

        inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('osmo-bsc')))

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
        pcap_recorder.PcapRecorder(self.testenv, self.run_dir.new_dir('pcap'), None, filter)

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        self.process = process.Process(self.name(), self.run_dir,
                                       (binary, '-c',
                                        os.path.abspath(self.config_file)),
                                       env=env)
        self.testenv.remember_to_stop(self.process)
        self.process.launch()

        self.vty = OsmoBscVty(self)
        self.vty.connect()

    def configure(self):
        self.config_file = self.run_dir.new_file('osmo-bsc.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(bsc=config.get_defaults('bsc'))
        config.overlay(values, self.testenv.suite().config())
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
        config.overlay(values, dict(bsc=dict(use_osmux=self.use_osmux)))

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

    def set_use_osmux(self, use=False, force=False):
        if not use:
            self.use_osmux = "off"
        else:
            if not force:
                self.use_osmux = "on"
            else:
                self.use_osmux = "only"

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

    def cleanup(self):
        if self.vty is not None:
            self.vty.disconnect()
            self.vty = None

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

class OsmoBscVty(osmo_vty.OsmoVty):
    def __init__(self, bsc, port=4242):
        self.bsc = bsc
        super().__init__(self.bsc.addr(), port)

    def get_active_lchans(self):
        lchan_summary = self.cmd('show lchan summary')

        re_lchan_summary = re.compile('BTS ([0-9]+), TRX ([0-9]+), Timeslot ([0-9]+) *([^,]*), Lchan ([0-9]+),.* State ([A-Za-z_]+).*')
        active_lchans = set()
        for line in lchan_summary:
            m = re_lchan_summary.match(line)
            if m:
                bts, trx, ts, lchan_type, subslot, state = m.groups()
                active_lchans.add('%s-%s-%s-%s %s %s' % (bts, trx, ts, subslot, lchan_type, state))
        if not active_lchans:
            self.dbg('No active lchans')
        else:
            self.dbg('Active lchans:\n|', '\n| '.join(active_lchans), '\n');
        return active_lchans

    def active_lchans_match(self, expected=[], not_expected=[]):
        active_lchans = self.get_active_lchans()
        matches = []
        mismatches = []

        for expected_lchan in expected:
            found = False
            for active_lchan in active_lchans:
                if active_lchan.startswith(expected_lchan):
                    found = True
                    break
            if found:
                matches.append(expected_lchan)
            else:
                mismatches.append('missing: ' + expected_lchan)

        for not_expected_lchan in not_expected:
            found = False
            for active_lchan in active_lchans:
                if active_lchan.startswith(not_expected_lchan):
                    found = True
                    break
            if not found:
                matches.append('not: ' + not_expected_lchan)
            else:
                mismatches.append('unexpected: ' + not_expected_lchan)

        if matches:
            self.log('Found matching lchan activity (%d of %d requirements):' % (len(matches), len(expected) + len(not_expected)), matches)
        if mismatches:
            self.err('Found unexpected lchan activity (%d of %d requirements):' % (len(mismatches), len(expected) + len(not_expected)), mismatches)
        return not mismatches

# vim: expandtab tabstop=4 shiftwidth=4
