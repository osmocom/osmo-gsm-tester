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
import tempfile
import re
from abc import ABCMeta, abstractmethod
from . import log, config, util, template, process, event_loop, pcap_recorder, bts, pcu
from . import powersupply

class NanoBts(bts.Bts):

    pwsup = None
    _pcu = None
##############
# PROTECTED
##############
    def __init__(self, suite_run, conf):
        if conf.get('addr') is None:
            raise log.Error('No attribute addr provided in conf!')
        super().__init__(suite_run, conf, 'nanobts_%s' % conf.get('addr'))

    def _configure(self):
        if self.bsc is None:
            raise log.Error('BTS needs to be added to a BSC or NITB before it can be configured')

        pwsup_opt = self.conf.get('power_supply', {})
        if not pwsup_opt:
            raise log.Error('No power_supply attribute provided in conf!')
        pwsup_type = pwsup_opt.get('type')
        if not pwsup_type:
            raise log.Error('No type attribute provided in power_supply conf!')

        self.pwsup = powersupply.get_instance_by_type(pwsup_type, pwsup_opt)

########################
# PUBLIC - INTERNAL API
########################

    def conf_for_bsc(self):
        values = config.get_defaults('bsc_bts')
        config.overlay(values, config.get_defaults('nanobts'))
        if self.lac is not None:
            config.overlay(values, { 'location_area_code': self.lac })
        if self.rac is not None:
            config.overlay(values, { 'routing_area_code': self.rac })
        if self.cellid is not None:
            config.overlay(values, { 'cell_identity': self.cellid })
        if self.bvci is not None:
            config.overlay(values, { 'bvci': self.bvci })
        config.overlay(values, self.conf)

        sgsn_conf = {} if self.sgsn is None else self.sgsn.conf_for_client()
        config.overlay(values, sgsn_conf)

        config.overlay(values, { 'osmobsc_bts_type': 'nanobts' })

        self.dbg(conf=values)
        return values


    def cleanup(self):
        if self.pwsup:
            self.dbg('Powering off NanoBTS')
            self.pwsup.power_set(False)

###################
# PUBLIC (test API included)
###################

    def start(self):
        for attr in ['net_device', 'ipa_unit_id']:
            if self.conf.get(attr) is None:
                raise log.Error('No attribute %s provided in conf!' % attr)
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self._configure()

        iface = self.conf.get('net_device')
        unitid = int(self.conf.get('ipa_unit_id'))
        bts_ip = self.remote_addr()

        # Make sure nanoBTS is powered and in a clean state:
        self.pwsup.power_cycle(1.0)

        pcap_recorder.PcapRecorder(self.suite_run, self.run_dir.new_dir('pcap'), iface,
                                   'host %s and port not 22' % self.remote_addr())

        self.log('Finding nanobts %s...' % bts_ip)
        ipfind = AbisIpFind(self.suite_run, self.run_dir, iface, 'preconf')
        ipfind.start()
        ipfind.wait_bts_ready(bts_ip)
        running_unitid = ipfind.get_unitid_by_ip(bts_ip)
        self.log('Found nanobts %s with unit_id %d' % (bts_ip, running_unitid))
        ipfind.stop()

        ipconfig = IpAccessConfig(self.suite_run, self.run_dir, bts_ip)
        if running_unitid != unitid:
            if not ipconfig.set_unit_id(unitid, False):
                raise log.Error('Failed configuring unit id %d' % unitid)
        # Apply OML IP and restart nanoBTS as it is required to apply the changes.
        if not ipconfig.set_oml_ip(self.bsc.addr(), True):
            raise log.Error('Failed configuring OML IP %s' % bts_ip)

        # Let some time for BTS to restart. It takes much more than 20 secs, and
        # this way we make sure we don't catch responses in abisip-find prior to
        # BTS restarting.
        event_loop.sleep(self, 20)

        self.log('Starting to connect to', self.bsc)
        ipfind = AbisIpFind(self.suite_run, self.run_dir, iface, 'postconf')
        ipfind.start()
        ipfind.wait_bts_ready(bts_ip)
        self.log('nanoBTS configured and running')
        ipfind.stop()

        event_loop.wait(self, self.bsc.bts_is_connected, self, timeout=600)
        self.log('nanoBTS connected to BSC')

        #According to roh, it can be configured to use a static IP in a permanent way:
        # 1- use abisip-find to find the default address
        # 2- use ./ipaccess-config --ip-address IP/MASK
        # 3- use ./ipaccess-config  --ip-gateway IP to set the IP of the main unit
        # 4- use ./ipaccess-config --restart to restart and apply the changes

        #Start must do the following:
        # 1- use abisip-find to find the default address
        # 2- use ./ipaccess-config --unit-id UNIT_ID
        # 3- use ./ipaccess-config --oml-ip --restart to set the IP of the BSC and apply+restart.
        # According to roh, using the 3 of them together was not reliable to work properly.

    def ready_for_pcu(self):
        """We don't really care as we use a Dummy PCU class."""
        return True

    def pcu(self):
        if not self._pcu:
            self._pcu = pcu.PcuDummy(self.suite_run, self, self.conf)
        return self._pcu


class AbisIpFind(log.Origin):
    suite_run = None
    parent_run_dir = None
    run_dir = None
    inst = None
    env = None
    iface = None
    proc = None

    BIN_ABISIP_FIND = 'abisip-find'
    BTS_UNIT_ID_RE = re.compile("Unit_ID='(?P<unit_id>\d+)/\d+/\d+'")

    def __init__(self, suite_run, parent_run_dir, iface, name_suffix):
        super().__init__(log.C_RUN, AbisIpFind.BIN_ABISIP_FIND + '-' + name_suffix)
        self.suite_run = suite_run
        self.parent_run_dir = parent_run_dir
        self.iface = iface
        self.env = {}

    def launch_process(self, binary_name, *args):
        binary = os.path.abspath(self.inst.child('bin', binary_name))
        run_dir = self.run_dir.new_dir(binary_name)
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        proc = process.Process(binary_name, run_dir,
                               (binary,) + args,
                               env=self.env)
        self.suite_run.remember_to_stop(proc)
        proc.launch()
        return proc

    def start(self):
        self.run_dir = util.Dir(self.parent_run_dir.new_dir(self.name()))
        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-bsc')))
        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in %r' % self.inst)
        ipfind_path = self.inst.child('bin', AbisIpFind.BIN_ABISIP_FIND)
        # setting capabilities will later disable use of LD_LIBRARY_PATH from ELF loader -> modify RPATH instead.
        self.log('Setting RPATH for', AbisIpFind.BIN_ABISIP_FIND)
        util.change_elf_rpath(ipfind_path, util.prepend_library_path(lib), self.run_dir.new_dir('patchelf'))
        # osmo-bty-octphy requires CAP_NET_RAW to open AF_PACKET socket:
        self.log('Applying CAP_NET_RAW capability to', AbisIpFind.BIN_ABISIP_FIND)
        util.setcap_net_raw(ipfind_path, self.run_dir.new_dir('setcap_net_raw'))
        self.proc = self.launch_process(AbisIpFind.BIN_ABISIP_FIND, self.iface)

    def stop(self):
        self.suite_run.stop_process(self.proc)

    def get_line_by_ip(self, ipaddr):
        """Get latest line (more up to date) from abisip-find based on ip address."""
        token = "IP_Address='%s'" % ipaddr
        myline = None
        for line in (self.proc.get_stdout() or '').splitlines():
            if token in line:
                myline = line
        return myline

    def get_unitid_by_ip(self, ipaddr):
            line = self.get_line_by_ip(ipaddr)
            if line is None:
                return None
            res = AbisIpFind.BTS_UNIT_ID_RE.search(line)
            if res:
                unit_id = int(res.group('unit_id'))
                return unit_id
            raise log.Error('abisip-find unit_id field for nanobts %s not found in %s' %(ipaddr, line))

    def bts_ready(self, ipaddr):
        return self.get_line_by_ip(ipaddr) is not None

    def wait_bts_ready(self, ipaddr):
        event_loop.wait(self, self.bts_ready, ipaddr)


class IpAccessConfig(log.Origin):
    suite_run = None
    parent_run_dir = None
    run_dir = None
    inst = None
    env = None
    bts_ip = None

    BIN_IPACCESS_CONFIG = 'ipaccess-config'

    def __init__(self, suite_run, parent_run_dir, bts_ip):
        super().__init__(log.C_RUN, IpAccessConfig.BIN_IPACCESS_CONFIG)
        self.suite_run = suite_run
        self.parent_run_dir = parent_run_dir
        self.bts_ip = bts_ip
        self.env = {}

    def launch_process(self, binary_name, *args):
        binary = os.path.abspath(self.inst.child('bin', binary_name))
        run_dir = self.run_dir.new_dir(binary_name)
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        proc = process.Process(binary_name, run_dir,
                               (binary,) + args,
                               env=self.env)
        proc.launch()
        return proc

    def run(self, name_suffix, *args):
        self.run_dir = util.Dir(self.parent_run_dir.new_dir(self.name()+'-'+name_suffix))
        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-bsc')))
        lib = self.inst.child('lib')
        self.env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }
        self.proc = self.launch_process(IpAccessConfig.BIN_IPACCESS_CONFIG, *args)
        try:
            event_loop.wait(self, self.proc.terminated)
        except Exception as e:
            self.proc.terminate()
            raise e
        return self.proc.result

    def set_unit_id(self, unitid, restart=False):
        if restart:
            retcode = self.run('unitid', '--restart', '--unit-id', '%d/0/0' % unitid, self.bts_ip)
        else:
            retcode = self.run('unitid', '--unit-id', '%d/0/0' % unitid, self.bts_ip)
        if retcode != 0:
            log.err('ipaccess-config --unit-id %d/0/0 returned error code %d' % (unitid, retcode))
        return retcode == 0

    def set_oml_ip(self, omlip, restart=False):
        if restart:
            retcode = self.run('oml', '--restart', '--oml-ip', omlip, self.bts_ip)
        else:
            retcode = self.run('oml', '--oml-ip', omlip, self.bts_ip)
        if retcode != 0:
            self.error('ipaccess-config --oml-ip %s returned error code %d' % (omlip, retcode))
        return retcode == 0

# vim: expandtab tabstop=4 shiftwidth=4
