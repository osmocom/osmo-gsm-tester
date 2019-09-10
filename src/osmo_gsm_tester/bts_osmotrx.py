# osmo_gsm_tester: specifics for running an osmo-bts-trx
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
import stat
import pprint
from abc import ABCMeta, abstractmethod
from . import log, config, util, template, process, bts_osmo
from . import powersupply
from .event_loop import MainLoop

class OsmoBtsTrx(bts_osmo.OsmoBtsMainUnit):
##############
# PROTECTED
##############

    BIN_BTS_TRX = 'osmo-bts-trx'
    BIN_PCU = 'osmo-pcu'

    CONF_BTS_TRX = 'osmo-bts-trx.cfg'

    def __init__(self, suite_run, conf):
        super().__init__(suite_run, conf, OsmoBtsTrx.BIN_BTS_TRX, 'osmo_bts_trx')
        self.run_dir = None
        self.inst = None
        self.trx = None
        self.pwsup_list = []
        self.env = {}
        self.gen_conf = {}

    def trx_remote_ip(self):
        conf_ip = self.conf.get('osmo_trx', {}).get('trx_ip', None)
        if conf_ip is not None:
            return conf_ip
        # if 'trx_remote_ip' is not configured, use same IP as BTS
        return self.remote_addr()

    def launch_process(self, keepalive, binary_name, *args):
        binary = os.path.abspath(self.inst.child('bin', binary_name))
        run_dir = self.run_dir.new_dir(binary_name)
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        proc = process.Process(binary_name, run_dir,
                               (binary,) + args,
                               env=self.env)
        self.suite_run.remember_to_stop(proc, keepalive)
        proc.launch()
        return proc

    def configure(self):
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be configured')
        self.config_file = self.run_dir.new_file(OsmoBtsTrx.CONF_BTS_TRX)
        self.dbg(config_file=self.config_file)

        values = dict(osmo_bts_trx=config.get_defaults('osmo_bts_trx'))
        config.overlay(values, dict(osmo_bts_trx=dict(osmo_trx=config.get_defaults('osmo_trx'))))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, {
                        'osmo_bts_trx': {
                            'oml_remote_ip': self.bsc.addr(),
                            'pcu_socket_path': self.pcu_socket_path(),
                            'osmo_trx': {
                                'bts_ip': self.remote_addr(),
                                'trx_ip': self.trx_remote_ip(),
                                'egprs': 'enable' if self.conf_for_bsc()['gprs_mode'] == 'egprs' else 'disable',
                                'channels': [{} for trx_i in range(self.num_trx())]
                            }
                        }
        })
        config.overlay(values, { 'osmo_bts_trx': self.conf })

        self.gen_conf = values
        self.dbg('OSMO-BTS-TRX CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(OsmoBtsTrx.CONF_BTS_TRX, values)
            self.dbg(r)
            f.write(r)

        self.pwsup_list = [None] * self.num_trx()
        # Construct trx_list appending with empty dicts if needed:
        conf_trx_list = self.conf.get('trx_list', [])
        conf_trx_list = conf_trx_list + [{}] * (self.num_trx() - len(conf_trx_list))
        for trx_i in range(self.num_trx()):
            pwsup_opt = conf_trx_list[trx_i].get('power_supply', {})
            if not pwsup_opt:
                self.dbg('no power_supply configured for TRX %d' % trx_i)
                continue
            pwsup_type = pwsup_opt.get('type')
            if not pwsup_type:
                raise log.Error('No type attribute provided in power_supply conf for TRX %d!' % trx_i)
            self.pwsup_list[trx_i] = powersupply.get_instance_by_type(pwsup_type, pwsup_opt)

    def launch_trx_enabled(self):
        return util.str2bool(self.gen_conf['osmo_bts_trx'].get('osmo_trx', {}).get('launch_trx'))

    def get_osmo_trx_type(self):
        return self.gen_conf['osmo_bts_trx'].get('osmo_trx', {}).get('type')

########################
# PUBLIC - INTERNAL API
########################
    def conf_for_bsc(self):
        values = self.conf_for_bsc_prepare()
        self.dbg(conf=values)
        return values

    def conf_for_osmotrx(self):
        return dict(osmo_trx=self.gen_conf['osmo_bts_trx'].get('osmo_trx', {}))

    def cleanup(self):
        i = 0
        for pwsup in self.pwsup_list:
            if pwsup:
                self.dbg('Powering off TRX %d' % i)
                pwsup.power_set(False)
            i = i + 1
        self.pwsup_list = []

###################
# PUBLIC (test API included)
###################
    def start(self, keepalive=False):
        if self.bsc is None:
            raise RuntimeError('BTS needs to be added to a BSC or NITB before it can be started')
        self.suite_run.poll()

        self.log('Starting to connect to', self.bsc)
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()

        # Power cycle all TRX if needed (right now only TRX0 for SC5):
        i = 0
        for pwsup in self.pwsup_list:
            if pwsup:
                self.dbg('Powering cycling TRX %d' % i)
                pwsup.power_cycle(1.0)
            i = i + 1

        if self.launch_trx_enabled():
            self.trx = OsmoTrx.get_instance_by_type(self.get_osmo_trx_type(), self.suite_run, self.conf_for_osmotrx())
            self.trx.start(keepalive)
            self.log('Waiting for %s to start up...' % self.trx.name())
            MainLoop.wait(self, self.trx.trx_ready)

        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-bts')))
        lib = self.inst.child('lib')
        if not os.path.isdir(lib):
            raise RuntimeError('No lib/ in %r' % self.inst)
        self.env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.proc_bts = self.launch_process(keepalive, OsmoBtsTrx.BIN_BTS_TRX, '-r', '1',
                            '-c', os.path.abspath(self.config_file),
                            '-i', self.bsc.addr())
        self.suite_run.poll()


################################################################################
# TRX
################################################################################

class Trx(log.Origin, metaclass=ABCMeta):
##############
# PROTECTED
##############
    def __init__(self, suite_run, conf, name):
        super().__init__(log.C_RUN, name)
        self.suite_run = suite_run
        self.conf = conf
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.listen_ip = conf.get('osmo_trx', {}).get('trx_ip')
        self.remote_user = conf.get('osmo_trx', {}).get('remote_user', None)

    @classmethod
    def get_instance_by_type(cls, type, suite_run, conf):
        KNOWN_OSMOTRX_TYPES = {
            'uhd': OsmoTrxUHD,
            'lms': OsmoTrxLMS,
            'sc5': TrxSC5
        }
        osmo_trx_class = KNOWN_OSMOTRX_TYPES.get(type)
        return osmo_trx_class(suite_run, conf)

##############
# PUBLIC (test API included)
##############
    @abstractmethod
    def start(self, keepalive=False):
        pass

    @abstractmethod
    def trx_ready(self):
        pass

class OsmoTrx(Trx, metaclass=ABCMeta):

    CONF_OSMO_TRX = 'osmo-trx.cfg'
    REMOTE_DIR = '/osmo-gsm-tester-trx/last_run'
    WRAPPER_SCRIPT = 'ssh_sigkiller.sh'

##############
# PROTECTED
##############
    def __init__(self, suite_run, conf):
        super().__init__(suite_run, conf, self.binary_name())
        self.env = {}
        self.log("OSMOTRX CONF: %r" % conf)
        self.bts_ip = conf.get('osmo_trx', {}).get('bts_ip')
        self.inst = None
        self.proc_trx = None

    @abstractmethod
    def binary_name(self):
        'Used by base class. Subclass can create different OsmoTRX implementations.'
        pass

    def configure(self):
        self.config_file = self.run_dir.new_file(OsmoTrx.CONF_OSMO_TRX)
        self.dbg(config_file=self.config_file)

        values = self.conf

        # we don't need to enable multi-arfcn for single channel
        if len(values.get('osmo_trx', {}).get('channels', [])) > 1:
            multi_arfcn_bool = util.str2bool(values.get('osmo_trx', {}).get('multi_arfcn', False))
        else:
            multi_arfcn_bool = False
        config.overlay(values, { 'osmo_trx': { 'multi_arfcn': multi_arfcn_bool } })

        self.dbg('OSMO-TRX CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(OsmoTrx.CONF_OSMO_TRX, values)
            self.dbg(r)
            f.write(r)

    def launch_process_local(self, keepalive, binary_name, *args):
        binary = os.path.abspath(self.inst.child('bin', binary_name))
        run_dir = self.run_dir.new_dir(binary_name)
        if not os.path.isfile(binary):
            raise RuntimeError('Binary missing: %r' % binary)
        proc = process.Process(binary_name, run_dir,
                               (binary,) + args,
                               env=self.env)
        self.suite_run.remember_to_stop(proc, keepalive)
        proc.launch()
        return proc

    def launch_process_remote(self, name, popen_args, remote_cwd=None, keepalive=False):
        run_dir = self.run_dir.new_dir(name)
        proc = process.RemoteProcess(name, run_dir, self.remote_user, self.listen_ip, remote_cwd,
                                     popen_args)
        self.suite_run.remember_to_stop(proc, keepalive)
        proc.launch()
        return proc

    def generate_wrapper_script(self):
        wrapper_script = self.run_dir.new_file(OsmoTrx.WRAPPER_SCRIPT)
        with open(wrapper_script, 'w') as f:
            r = """#!/bin/bash
            mypid=0
            sign_handler() {
                    sig=$1
                    echo "received signal handler $sig, killing $mypid"
                    kill $mypid
            }
            trap 'sign_handler SIGTERM' SIGTERM
            trap 'sign_handler SIGINT' SIGINT
            trap 'sign_handler SIGHUP' SIGHUP
            "$@" &
            mypid=$!
            echo "waiting for $mypid"
            wait $mypid
            echo "process $mypid finished"
            """
            f.write(r)
        st = os.stat(wrapper_script)
        os.chmod(wrapper_script, st.st_mode | stat.S_IEXEC)
        return wrapper_script

##############
# PUBLIC (test API included)
##############
    def start(self, keepalive=False):
        self.configure()
        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-trx')))
        if not self.remote_user:
            # Run locally if ssh user is not set
            lib = self.inst.child('lib')
            self.env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }
            self.proc_trx = self.launch_process_local(keepalive, self.binary_name(),
                                            '-C', os.path.abspath(self.config_file))
        else:
            # Run remotely through ssh. We need to run osmo-trx under a wrapper
            # script since osmo-trx ignores SIGHUP and will keep running after
            # we close local ssh session. The wrapper script catches SIGHUP and
            # sends SIGINT to it.
            wrapper_script = self.generate_wrapper_script()
            remote_run_dir = util.Dir(OsmoTrx.REMOTE_DIR)
            self.remote_inst = process.copy_inst_ssh(self.run_dir, self.inst, remote_run_dir, self.remote_user,
                                                self.listen_ip, self.binary_name(), self.config_file)
            remote_wrapper_script = remote_run_dir.child(OsmoTrx.WRAPPER_SCRIPT)
            remote_config_file = remote_run_dir.child(OsmoTrx.CONF_OSMO_TRX)
            remote_lib = self.remote_inst.child('lib')
            remote_binary = self.remote_inst.child('bin', self.binary_name())
            process.scp(self.run_dir, self.remote_user, self.listen_ip, 'scp-wrapper-to-remote', wrapper_script, remote_wrapper_script)

            args = ('LD_LIBRARY_PATH=%s' % remote_lib, remote_wrapper_script, remote_binary, '-C', remote_config_file)
            self.proc_trx = self.launch_process_remote(self.binary_name(), args, remote_cwd=remote_run_dir, keepalive=keepalive)

    def trx_ready(self):
        if not self.proc_trx or not self.proc_trx.is_running:
            return False
        return '-- Transceiver active with' in (self.proc_trx.get_stdout() or '')

class OsmoTrxUHD(OsmoTrx):
    BIN_TRX = 'osmo-trx-uhd'

    def __init__(self, suite_run, conf):
        super().__init__(suite_run, conf)

    def binary_name(self):
        return OsmoTrxUHD.BIN_TRX

class OsmoTrxLMS(OsmoTrx):
    BIN_TRX = 'osmo-trx-lms'

    def __init__(self, suite_run, conf):
        super().__init__(suite_run, conf)
        self.conf['osmo_trx']['channels'][0]['rx_path'] = 'LNAW'

    def binary_name(self):
        return OsmoTrxLMS.BIN_TRX

class TrxSC5(Trx):

    def __init__(self, suite_run, conf):
        super().__init__(suite_run, conf, "sc5-trx")
        self.ready = False

    def start(self, keepalive=False):
        name = "ssh_sc5_ccli"
        run_dir = self.run_dir.new_dir(name)
        popen_args = ('/cx/bin/ccli', '-c', 'gsm.unlock')
        proc = process.RemoteProcess(name, run_dir, self.remote_user, self.listen_ip, None,
                                     popen_args)
        keep_trying = 10
        while keep_trying > 0:
            if proc.respawn_sync(raise_nonsuccess=False) == 0 and 'OK' in (proc.get_stdout() or ''):
                break
            keep_trying = keep_trying - 1
            self.log('Configuring SC5 TRX failed, retrying %d more times' % keep_trying)
            MainLoop.sleep(self, 5)
        if keep_trying == 0:
            raise log.Error('Failed configuring SC5!')
        self.ready = True

    def trx_ready(self):
        return self.ready

# vim: expandtab tabstop=4 shiftwidth=4
