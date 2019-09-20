# osmo_gsm_tester: specifics for running an ip.access nanoBTS
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

import os
import pprint
import re
from . import log, config, util, process, pcap_recorder, abisipfind
from . import powersupply
from .event_loop import MainLoop

class HnbNano3g(log.Origin):

    SSH_USER='root'
    IPA_DMI_PATH='/opt/ipaccess/DMI/ipa-dmi'
##############
# PROTECTED
##############
    def __init__(self, suite_run, conf):
        super().__init__(log.C_RUN, 'nano3g_%s' % conf.get('label', 'nolabel'), 'nanobts')
        self.suite_run = suite_run
        self.conf = conf
        self.pwsup = None
        self.hnbgw = None
        self.lac = None
        self.rac = None
        self.cellid = None

    def _configure(self):
        if self.hnbgw is None:
            raise log.Error('HNodeB needs to be added to a HNBGW before it can be configured')

        values = dict(hnb=config.get_defaults('hnb'))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, { 'hnb': self.conf })
        self.gen_conf = values
        self.dbg('OSMO-BTS-TRX CONFIG:\n' + pprint.pformat(values))

        pwsup_opt = self.conf.get('power_supply', {})
        if not pwsup_opt:
            raise log.Error('No power_supply attribute provided in conf!')
        pwsup_type = pwsup_opt.get('type')
        if not pwsup_type:
            raise log.Error('No type attribute provided in power_supply conf!' % trx_i)
        self.pwsup = powersupply.get_instance_by_type(pwsup_type, pwsup_opt)

    def wait_ready(self, local_bind_ip, hnb_ip):
        self.log('Finding nano3g %s, binding on %s...' % (hnb_ip, local_bind_ip))
        ipfind = abisipfind.AbisIpFind(self.suite_run, self.run_dir, local_bind_ip, 'preconf')
        ipfind.start()
        ipfind.wait_bts_ready(hnb_ip)
        running_unitid, running_trx = ipfind.get_unitid_by_ip(hnb_ip)
        self.log('Found nano3g %s with unit_id %d trx %d' % (hnb_ip, running_unitid, running_trx))
        ipfind.stop()

    def run_ssh_cmd(self, name, popen_args):
        # On OpenSSH >= 7.0, only-supported algos by nano3g are disabled by default, they need to be enabled manually:
        # https://projects.osmocom.org/projects/cellular-infrastructure/wiki/Configuring_the_ipaccess_nano3G#SSH-Access
        ssh_args=['-o', 'KexAlgorithms=+diffie-hellman-group1-sha1', '-c', 'aes128-cbc']
        process.run_remote_sync(self.run_dir, HnbNano3g.SSH_USER, self.addr(), name, popen_args, remote_cwd=None, ssh_args=ssh_args)

    def run_dmi_cmd(self, name, cmd_str):
        self.run_ssh_cmd('dmi-' + name, (HnbNano3g.IPA_DMI_PATH, '-c', '\"%s\"' % cmd_str))

    def run_reboot(self):
        self.run_ssh_cmd('reboot', reboot)

    def set_permanent_settings(self):
        # These settings are set permantently and require a reboot after set:
        self.run_dmi_cmd('set_mcc', 'set mcc=%s' % self.gen_conf['hnb']['net']['mcc'])
        self.run_dmi_cmd('set_mnc', 'set mnc=%s' % self.gen_conf['hnb']['net']['mnc'])
        # [uarfcnDownlink, 1900 MHz band], [scramblingCode], [dummyCellId]
        self.run_dmi_cmd('set_rfparams', 'set rfParamsCandidateList=({%s, 401, %d})' % (self.gen_conf['hnb']['net']['uarfcn'], self.cellid))
        # [lac], [rac]
        self.run_dmi_cmd('set_lac', 'set lacRacCandidateList=({%d, (%d)})' % (self.lac, self.rac))
        self.run_dmi_cmd('set_hnbcid', 'set hnbCId=%d',  self.cellid)
        self.run_dmi_cmd('set_rncid', 'set rncIdentity=0')

    def set_volatile_settings(self):
        self.run_dmi_cmd('set_hnbgwaddr', 'set hnbGwAddress=%s' % self.addr())
        self.run_dmi_cmd('action_2061', 'action 2061')
        self.run_dmi_cmd('action_1216', 'action 1216')
        self.run_dmi_cmd('action_establish_conn', 'action establishPermanentHnbGwConnection')
        self.run_dmi_cmd('set_csgaccessmode', 'set csgAccessMode=CSG_ACCESS_MODE_OPEN_ACCESS')

########################
# PUBLIC - INTERNAL API
#######################

    def set_lac(self, lac):
        self.lac = lac

    def set_rac(self, rac):
        self.rac = rac

    def set_cellid(self, cellid):
        self.cellid = cellid

    def cleanup(self):
        if self.pwsup:
            self.dbg('Powering off')
            self.pwsup.power_set(False)
        self.pwsup = None

###################
# PUBLIC (test API included)
###################

    def start(self):
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self._configure()

        hnb_ip = self.addr()

        # Make sure nano3g is powered and in a clean state:
        self.dbg('Powering cycling nano3g')
        self.pwsup.power_cycle(1.0)

        pcap_recorder.PcapRecorder(self.suite_run, self.run_dir.new_dir('pcap'), None,
                                   'host %s and port not 22' % hnb_ip)

        # This fine for now, however concurrent tests using nano3g may run into "address already in use" since dst is broadcast.
        # Once concurrency is needed, a new config attr should be added to have an extra static IP assigned on the main-unit to each Nano3g resource.
        local_bind_ip = util.dst_ip_get_local_bind(hnb_ip)

        # Wait until nano3g is ready (announcing through abisip-find) and then set permanent settings
        self.wait_ready(local_bind_ip, hnb_ip)
        self.set_permanent_settings()

        # Configs applied above require a reboot of the nano3g to be applied:
        self.run_reboot()
        #sleep a few seconds (to avoid getting abisipind results previous to reboot):
        MainLoop.sleep(self, 5.0)

        # Wait until nano3g is ready again and apply volatile settings:
        self.wait_ready(local_bind_ip, hnb_ip)
        self.set_volatile_settings()

        # After applying volatile settings, nano3g should end up connected to our HNBGW:
        MainLoop.wait(self, self.hnbgw.hnb_is_connected, self, timeout=600)
        self.log('nano3g connected to HNBGW')

    def addr(self):
        return self.conf.get('addr')

    def set_hnbgw(self, hnbgw):
        self.hnbgw = hnbgw

# vim: expandtab tabstop=4 shiftwidth=4
