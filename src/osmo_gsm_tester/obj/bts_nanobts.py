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
import re
import json
from ..core import log, config, util, process
from ..core.event_loop import MainLoop
from . import pcap_recorder, bts, pcu
from . import powersupply

class NanoBts(bts.Bts):

##############
# PROTECTED
##############
    def __init__(self, testenv, conf):
        super().__init__(testenv, conf, 'nanobts_%s' % conf.get('label', 'nolabel'), 'nanobts')
        self.pwsup_list = []
        self._pcu = None

    def _configure(self):
        if self.bsc is None:
            raise log.Error('BTS needs to be added to a BSC or NITB before it can be configured')

        for trx_i in range(self.num_trx()):
            pwsup_opt = self.conf.get('trx_list')[trx_i].get('power_supply', {})
            if not pwsup_opt:
                raise log.Error('No power_supply attribute provided in conf for TRX %d!' % trx_i)
            pwsup_type = pwsup_opt.get('type')
            if not pwsup_type:
                raise log.Error('No type attribute provided in power_supply conf for TRX %d!' % trx_i)
            self.pwsup_list.append(powersupply.get_instance_by_type(pwsup_type, pwsup_opt))


    def get_pcap_filter_all_trx_ip(self):
        ret = "("
        for trx_i in range(self.num_trx()):
            if trx_i != 0:
                ret = ret + " or "
            bts_trx_ip = self.conf.get('trx_list')[trx_i].get('addr')
            ret = ret + "host " + bts_trx_ip
        ret = ret + ")"
        return ret

########################
# PUBLIC - INTERNAL API
########################

    def conf_for_bsc(self):
        values = self.conf_for_bsc_prepare()
        # Hack until we have proper ARFCN resource allocation support (OS#2230)
        band = values.get('band')
        trx_list = values.get('trx_list')
        if band == 'GSM-1900':
            for trx_i in range(len(trx_list)):
                config.overlay(trx_list[trx_i], { 'arfcn' : str(531 + trx_i * 2) })
        elif band == 'GSM-900':
            for trx_i in range(len(trx_list)):
                config.overlay(trx_list[trx_i], { 'arfcn' : str(50 + trx_i * 2) })

        config.overlay(values, { 'osmobsc_bts_type': 'nanobts' })

        self.dbg(conf=values)
        return values


    def cleanup(self):
        for pwsup in self.pwsup_list:
            self.dbg('Powering off NanoBTS TRX')
            pwsup.power_set(False)
        self.pwsup_list = []

###################
# PUBLIC (test API included)
###################

    def start(self, keepalive=False):
        if self.conf.get('ipa_unit_id') is None:
            raise log.Error('No attribute ipa_unit_id provided in conf!')
        self.run_dir = util.Dir(self.testenv.suite().get_run_dir().new_dir(self.name()))
        self._configure()

        unitid = int(self.conf.get('ipa_unit_id'))

        # Make sure all nanoBTS TRX are powered and in a clean state:
        for pwsup in self.pwsup_list:
            self.dbg('Powering cycling NanoBTS TRX')
            pwsup.power_cycle(1.0)

        pcap_recorder.PcapRecorder(self.testenv, self.run_dir.new_dir('pcap'), None,
                                   '%s and port not 22' % self.get_pcap_filter_all_trx_ip())


        # TODO: If setting N TRX, we should set up them in parallel instead of waiting for each one.
        for trx_i in range(self.num_trx()):
            bts_trx_ip = self.conf.get('trx_list')[trx_i].get('addr')
            # This fine for now, however concurrent tests using Nanobts may run into "address already in use" since dst is broadcast.
            # Once concurrency is needed, a new config attr should be added to have an extra static IP assigned on the main-unit to each Nanobts resource.
            local_bind_ip = util.dst_ip_get_local_bind(bts_trx_ip)

            self.log('Finding nanobts %s, binding on %s...' % (bts_trx_ip, local_bind_ip))
            ipfind = AbisIpFind(self.testenv, self.run_dir, local_bind_ip, 'preconf')
            ipfind.start()
            ipfind.wait_bts_ready(bts_trx_ip)
            running_unitid, running_trx = ipfind.get_unitid_by_ip(bts_trx_ip)
            self.log('Found nanobts %s with unit_id %d trx %d' % (bts_trx_ip, running_unitid, running_trx))
            ipfind.stop()

            ipconfig = IpAccessConfig(self.testenv, self.run_dir, bts_trx_ip)
            running_oml_ip = ipconfig.get_oml_ip()

            if running_unitid != unitid or running_trx != trx_i:
                if not ipconfig.set_unit_id(unitid, trx_i, False):
                    raise log.Error('Failed configuring unit id %d trx %d' % (unitid, trx_i))

            if running_oml_ip != self.bsc.addr():
                # Apply OML IP and restart nanoBTS as it is required to apply the changes.
                self.dbg('Current OML IPaddr "%s" does not match BSC IPaddr "%s", reconfiguring and restarting it' % (running_oml_ip, self.bsc.addr()))
                if not ipconfig.set_oml_ip(self.bsc.addr(), True):
                    raise log.Error('Failed configuring OML IP %s' % bts_trx_ip)

                # Let some time for BTS to restart. It takes much more than 20 secs, and
                # this way we make sure we don't catch responses in abisip-find prior to
                # BTS restarting.
                MainLoop.sleep(self, 20)

                self.dbg('Starting to connect id %d trx %d to' % (unitid, trx_i), self.bsc)
                ipfind = AbisIpFind(self.testenv, self.run_dir, local_bind_ip, 'postconf')
                ipfind.start()
                ipfind.wait_bts_ready(bts_trx_ip)
                self.log('nanoBTS id %d trx %d configured and running' % (unitid, trx_i))
                ipfind.stop()
            else:
                self.dbg('nanoBTS id %d trx %d no need to change OML IP (%s) and restart' % (unitid, trx_i, running_oml_ip))

        MainLoop.wait(self, self.bsc.bts_is_connected, self, timeout=600)
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
            self._pcu = pcu.PcuDummy(self.testenv, self, self.conf)
        return self._pcu


class AbisIpFind(log.Origin):
    testenv = None
    parent_run_dir = None
    run_dir = None
    inst = None
    env = None
    bind_ip = None
    proc = None

    BIN_ABISIP_FIND = 'abisip-find'
    BTS_UNIT_ID_RE = re.compile("Unit_ID='(?P<unit_id>\d+)/\d+/(?P<trx_id>\d+)'")

    def __init__(self, testenv, parent_run_dir, bind_ip, name_suffix):
        super().__init__(log.C_RUN, AbisIpFind.BIN_ABISIP_FIND + '-' + name_suffix)
        self.testenv = testenv
        self.parent_run_dir = parent_run_dir
        self.bind_ip = bind_ip
        self.env = {}

    def start(self):
        self.run_dir = util.Dir(self.parent_run_dir.new_dir(self.name()))
        self.inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('osmo-bsc')))

        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise log.Error('No lib/ in %r' % self.inst)
        ipfind_path = self.inst.child('bin', AbisIpFind.BIN_ABISIP_FIND)
        if not os.path.isfile(ipfind_path):
            raise RuntimeError('Binary missing: %r' % ipfind_path)

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }
        self.proc = process.Process(self.name(), self.run_dir,
                            (ipfind_path, '-i', '1', '-b', self.bind_ip),
                            env=env)
        self.testenv.remember_to_stop(self.proc)
        self.proc.launch()

    def stop(self):
        self.testenv.stop_process(self.proc)

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
                trx_id = int(res.group('trx_id'))
                return (unit_id, trx_id)
            raise log.Error('abisip-find unit_id field for nanobts %s not found in %s' %(ipaddr, line))

    def bts_ready(self, ipaddr):
        return self.get_line_by_ip(ipaddr) is not None

    def wait_bts_ready(self, ipaddr):
        MainLoop.wait(self, self.bts_ready, ipaddr)
        # There's a period of time after boot in which nanobts answers to
        # abisip-find but tcp RSTs ipacces-config conns. Let's wait in here a
        # bit more time to avoid failing after stating the BTS is ready.
        MainLoop.sleep(self, 2)

class IpAccessConfig(log.Origin):
    testenv = None
    parent_run_dir = None
    run_dir = None
    inst = None
    env = None
    bts_ip = None

    BIN_IPACCESS_CONFIG = 'ipaccess-config'

    def __init__(self, testenv, parent_run_dir, bts_ip):
        super().__init__(log.C_RUN, IpAccessConfig.BIN_IPACCESS_CONFIG)
        self.testenv = testenv
        self.parent_run_dir = parent_run_dir
        self.bts_ip = bts_ip
        self.env = {}

    def create_process(self, binary_name, *args):
        binary = os.path.abspath(self.inst.child('bin', binary_name))
        run_dir = self.run_dir.new_dir(binary_name)
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        proc = process.Process(binary_name, run_dir,
                               (binary,) + args,
                               env=self.env)
        return proc

    def run(self, name_suffix, *args):
        self.run_dir = util.Dir(self.parent_run_dir.new_dir(self.name()+'-'+name_suffix))
        self.inst = util.Dir(os.path.abspath(self.testenv.suite().trial().get_inst('osmo-bsc')))
        lib = self.inst.child('lib')
        self.env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }
        self.proc = self.create_process(IpAccessConfig.BIN_IPACCESS_CONFIG, *args)
        return self.proc.launch_sync(raise_nonsuccess=False)

    def set_unit_id(self, unitid, trx_num, restart=False):
        uid_str = '%d/0/%d' % (unitid, trx_num)
        if restart:
            retcode = self.run('setunitid', '--restart', '--unit-id', '%s' % uid_str, self.bts_ip)
        else:
            retcode = self.run('setunitid', '--unit-id', '%s' % uid_str, self.bts_ip)
        if retcode != 0:
            self.err('ipaccess-config --unit-id %s returned error code %d' % (uid_str, retcode))
        return retcode == 0

    def set_oml_ip(self, omlip, restart=False):
        if restart:
            retcode = self.run('setoml', '--restart', '--oml-ip', omlip, self.bts_ip)
        else:
            retcode = self.run('setoml', '--oml-ip', omlip, self.bts_ip)
        if retcode != 0:
            self.error('ipaccess-config --oml-ip %s returned error code %d' % (omlip, retcode))
        return retcode == 0

    def get_oml_ip(self):
        retcode = self.run('getoml', '-q', '-G', self.bts_ip)
        if retcode != 0:
            raise log.Error('ipaccess-config -q -G %s returned error code %d' % (self.bts_ip, retcode))
        output = self.proc.get_stdout()
        # Our logging system adds "launched on" line at the start, so let's skip until the json code:
        output_json = output[output.index('{'):]
        json_data = json.loads(output_json)
        return json_data['primary_oml_ip']

# vim: expandtab tabstop=4 shiftwidth=4
