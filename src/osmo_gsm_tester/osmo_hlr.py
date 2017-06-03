# osmo_gsm_tester: specifics for running an osmo-hlr
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

class OsmoHlr(log.Origin):
    suite_run = None
    ip_address = None
    run_dir = None
    config_file = None
    process = None
    next_subscriber_id = 1

    def __init__(self, suite_run, ip_address):
        self.suite_run = suite_run
        self.ip_address = ip_address
        self.set_log_category(log.C_RUN)
        self.set_name('osmo-hlr_%s' % ip_address.get('addr'))
        self.bts = []

    def start(self):
        self.log('Starting osmo-hlr')
        self.run_dir = util.Dir(self.suite_run.trial.get_run_dir().new_dir(self.name()))
        self.configure()

        inst = util.Dir(os.path.abspath(self.suite_run.trial.get_inst('osmo-hlr')))

        binary = inst.child('bin', 'osmo-hlr')
        if not os.path.isfile(binary):
            self.raise_exn('Binary missing:', binary)
        lib = inst.child('lib')
        if not os.path.isdir(lib):
            self.raise_exn('No lib/ in', inst)

        # bootstrap an empty hlr.db
        self.db_file = self.run_dir.new_file('hlr.db')
        sql_input = inst.child('share/doc/osmo-hlr/hlr.sql')
        if not os.path.isfile(sql_input):
            self.raise_exn('hlr.sql missing:', sql_input)
        self.run_local('create_hlr_db', ('/bin/sh', '-c', 'sqlite3 %r < %r' % (self.db_file, sql_input)))

        iface = util.ip_to_iface(self.addr())
        pcap_recorder.PcapRecorder(self.suite_run, self.run_dir.new_dir('pcap'), iface,
                                   'host %s' % self.addr())

        env = { 'LD_LIBRARY_PATH': util.prepend_library_path(lib) }

        self.dbg(run_dir=self.run_dir, binary=binary, env=env)
        self.process = process.Process(self.name(), self.run_dir,
                                       (binary,
                                        '-c', os.path.abspath(self.config_file),
                                        '--database', self.db_file),
                                       env=env)
        self.suite_run.remember_to_stop(self.process)
        self.process.launch()

    def configure(self):
        self.config_file = self.run_dir.new_file('osmo-hlr.cfg')
        self.dbg(config_file=self.config_file)

        values = dict(hlr=config.get_defaults('hlr'))
        config.overlay(values, self.suite_run.config())
        config.overlay(values, dict(hlr=dict(ip_address=self.ip_address)))

        self.dbg('HLR CONFIG:\n' + pprint.pformat(values))

        with open(self.config_file, 'w') as f:
            r = template.render('osmo-hlr.cfg', values)
            self.dbg(r)
            f.write(r)

    def addr(self):
        return self.ip_address.get('addr')

    def running(self):
        return not self.process.terminated()

    def run_local(self, name, popen_args):
        with self:
            run_dir = self.run_dir.new_dir(name)
            proc = process.Process(name, run_dir, popen_args)
            proc.launch()
            proc.wait()
            if proc.result != 0:
                proc.raise_exn('Exited in error')

    def run_sql_file(self, name, sql_file):
        self.run_local(name, ('/bin/sh', '-c', 'sqlite3 %r < %r' % (self.db_file, sql_file)))

    def run_sql(self, name, sql):
        self.dbg('SQL:', repr(sql))
        sql_file = self.run_dir.new_file(name + '.sql')
        with open(sql_file, 'w') as f:
            f.write(sql)
        self.run_sql_file(name, sql_file)

    def subscriber_add(self, modem, msisdn=None):
        if msisdn is None:
            msisdn = self.suite_run.resources_pool.next_msisdn(modem)
        modem.set_msisdn(msisdn)
        subscriber_id = self.next_subscriber_id
        self.next_subscriber_id += 1
        self.log('Add subscriber', msisdn=msisdn, imsi=modem.imsi(), subscriber_id=subscriber_id)
        self.run_sql('add_subscriber',
            'insert into subscriber (id, imsi, msisdn) values (%r, %r, %r);'
            % (subscriber_id, modem.imsi(), modem.msisdn))
        return subscriber_id

# vim: expandtab tabstop=4 shiftwidth=4
