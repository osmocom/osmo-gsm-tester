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
import pprint
import tempfile
from abc import ABCMeta, abstractmethod
from . import log, config, util, template, process, pcu_osmo, bts_osmo
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
                                'channels': [{}] # TODO: implement channels for multiTRX
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

class OsmoTrx(log.Origin, metaclass=ABCMeta):

    CONF_OSMO_TRX = 'osmo-trx.cfg'

##############
# PROTECTED
##############
    def __init__(self, suite_run, conf):
        super().__init__(log.C_RUN, self.binary_name())
        self.suite_run = suite_run
        self.conf = conf
        self.env = {}
        self.listen_ip = conf.get('trx_ip')
        self.bts_ip = conf.get('bts_ip')
        self.run_dir = None
        self.inst = None
        self.proc_trx = None

    @classmethod
    def get_instance_by_type(cls, type, suite_run, conf):
        KNOWN_OSMOTRX_TYPES = {
            'uhd': OsmoTrxUHD,
        }
        osmo_trx_class = KNOWN_OSMOTRX_TYPES.get(type)
        return osmo_trx_class(suite_run, conf)

    @abstractmethod
    def binary_name(self):
        'Used by base class. Subclass can create different OsmoTRX implementations.'
        pass

    def configure(self):
        self.config_file = self.run_dir.new_file(OsmoTrx.CONF_OSMO_TRX)
        self.dbg(config_file=self.config_file)

        values = self.conf

        self.dbg('OSMO-TRX CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render(OsmoTrx.CONF_OSMO_TRX, values)
            self.dbg(r)
            f.write(r)

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

##############
# PUBLIC (test API included)
##############
    def start(self, keepalive=False):
        self.run_dir = util.Dir(self.suite_run.get_test_run_dir().new_dir(self.name()))
        self.configure()
        self.inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-trx')))
        lib = self.inst.child('lib')
        self.env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }
        self.proc_trx = self.launch_process(keepalive, self.binary_name(),
                                            '-C', os.path.abspath(self.config_file))

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

# vim: expandtab tabstop=4 shiftwidth=4
