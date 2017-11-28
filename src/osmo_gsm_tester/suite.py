# osmo_gsm_tester: test suite
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
import sys
import time
import pprint
from . import config, log, template, util, resource, schema, event_loop, test
from . import osmo_nitb, osmo_hlr, osmo_mgcpgw, osmo_mgw, osmo_msc, osmo_bsc, osmo_stp, osmo_ggsn, osmo_sgsn, modem, esme

class Timeout(Exception):
    pass

class SuiteDefinition(log.Origin):
    '''A test suite reserves resources for a number of tests.
       Each test requires a specific number of modems, BTSs etc., which are
       reserved beforehand by a test suite. This way several test suites can be
       scheduled dynamically without resource conflicts arising halfway through
       the tests.'''

    CONF_FILENAME = 'suite.conf'

    def __init__(self, suite_dir):
        self.suite_dir = suite_dir
        super().__init__(log.C_CNF, os.path.basename(self.suite_dir))
        self.read_conf()

    def read_conf(self):
        self.dbg('reading %s' % SuiteDefinition.CONF_FILENAME)
        if not os.path.isdir(self.suite_dir):
            raise RuntimeError('No such directory: %r' % self.suite_dir)
        self.conf = config.read(os.path.join(self.suite_dir,
                                             SuiteDefinition.CONF_FILENAME),
                                resource.CONF_SCHEMA)
        self.load_test_basenames()

    def load_test_basenames(self):
        self.test_basenames = []
        for basename in sorted(os.listdir(self.suite_dir)):
            if not basename.endswith('.py'):
                continue
            self.test_basenames.append(basename)

class SuiteRun(log.Origin):
    UNKNOWN = 'UNKNOWN'
    PASS = 'PASS'
    FAIL = 'FAIL'

    trial = None
    status = None
    start_timestamp = None
    duration = None
    resources_pool = None
    reserved_resources = None
    objects_to_clean_up = None
    _resource_requirements = None
    _config = None
    _processes = None
    _run_dir = None

    def __init__(self, trial, suite_scenario_str, suite_definition, scenarios=[]):
        super().__init__(log.C_TST, suite_scenario_str)
        self.trial = trial
        self.definition = suite_definition
        self.scenarios = scenarios
        self.resources_pool = resource.ResourcesPool()
        self.status = SuiteRun.UNKNOWN
        self.load_tests()

    def load_tests(self):
        self.tests = []
        for test_basename in self.definition.test_basenames:
            self.tests.append(test.Test(self, test_basename))

    def register_for_cleanup(self, *obj):
        assert all([hasattr(o, 'cleanup') for o in obj])
        self.objects_to_clean_up = self.objects_to_clean_up or []
        self.objects_to_clean_up.extend(obj)

    def objects_cleanup(self):
        while self.objects_to_clean_up:
            obj = self.objects_to_clean_up.pop()
            try:
                obj.cleanup()
            except Exception:
                log.log_exn()

    def mark_start(self):
        self.start_timestamp = time.time()
        self.duration = 0
        self.status = SuiteRun.UNKNOWN

    def combined(self, conf_name):
        log.dbg(combining=conf_name)
        log.ctx(combining_scenarios=conf_name)
        combination = config.replicate_times(self.definition.conf.get(conf_name, {}))
        log.dbg(definition_conf=combination)
        for scenario in self.scenarios:
            log.ctx(combining_scenarios=conf_name, scenario=scenario.name())
            c = config.replicate_times(scenario.get(conf_name, {}))
            log.dbg(scenario=scenario.name(), conf=c)
            if c is None:
                continue
            config.combine(combination, c)
        return combination

    def get_run_dir(self):
        if self._run_dir is None:
            self._run_dir = util.Dir(self.trial.get_run_dir().new_dir(self.name()))
        return self._run_dir

    def get_test_run_dir(self):
        if self.current_test:
            return self.current_test.get_run_dir()
        return self.get_run_dir()

    def resource_requirements(self):
        if self._resource_requirements is None:
            self._resource_requirements = self.combined('resources')
        return self._resource_requirements

    def config(self):
        if self._config is None:
            self._config = self.combined('config')
        return self._config

    def reserve_resources(self):
        if self.reserved_resources:
            raise RuntimeError('Attempt to reserve resources twice for a SuiteRun')
        self.log('reserving resources in', self.resources_pool.state_dir, '...')
        self.reserved_resources = self.resources_pool.reserve(self, self.resource_requirements())

    def run_tests(self, names=None):
        try:
            log.large_separator(self.trial.name(), self.name(), sublevel=2)
            self.mark_start()
            event_loop.register_poll_func(self.poll)
            if not self.reserved_resources:
                self.reserve_resources()
            for t in self.tests:
                if names and not t.name() in names:
                    t.set_skip()
                    continue
                self.current_test = t
                t.run()
                self.stop_processes()
                self.objects_cleanup()
                self.reserved_resources.put_all()
        except Exception:
            log.log_exn()
        except BaseException as e:
            # when the program is aborted by a signal (like Ctrl-C), escalate to abort all.
            self.err('SUITE RUN ABORTED: %s' % type(e).__name__)
            raise
        finally:
            # if sys.exit() called from signal handler (e.g. SIGINT), SystemExit
            # base exception is raised. Make sure to stop processes in this
            # finally section. Resources are automatically freed with 'atexit'.
            self.stop_processes()
            self.objects_cleanup()
            self.free_resources()
            event_loop.unregister_poll_func(self.poll)
            self.duration = time.time() - self.start_timestamp

            passed, skipped, failed = self.count_test_results()
            # if no tests ran, count it as failure
            if passed and not failed:
                self.status = SuiteRun.PASS
            else:
                self.status = SuiteRun.FAIL

            log.large_separator(self.trial.name(), self.name(), self.status, sublevel=2, space_above=False)

    def passed(self):
        return self.status == SuiteRun.PASS

    def count_test_results(self):
        passed = 0
        skipped = 0
        failed = 0
        for t in self.tests:
            if t.status == test.Test.PASS:
                passed += 1
            elif t.status == test.Test.FAIL:
                failed += 1
            else:
                skipped += 1
        return (passed, skipped, failed)

    def remember_to_stop(self, process):
        if self._processes is None:
            self._processes = []
        self._processes.insert(0, process)

    def stop_processes(self):
        while self._processes:
            self._processes.pop().terminate()

    def free_resources(self):
        if self.reserved_resources is None:
            return
        self.reserved_resources.free()

    def ip_address(self, specifics=None):
        return self.reserved_resources.get(resource.R_IP_ADDRESS, specifics=specifics)

    def nitb(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return osmo_nitb.OsmoNitb(self, ip_address)

    def hlr(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return osmo_hlr.OsmoHlr(self, ip_address)

    def ggsn(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return osmo_ggsn.OsmoGgsn(self, ip_address)

    def sgsn(self, hlr, ggsn, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return osmo_sgsn.OsmoSgsn(self, hlr, ggsn, ip_address)

    def mgcpgw(self, ip_address=None, bts_ip=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return osmo_mgcpgw.OsmoMgcpgw(self, ip_address, bts_ip)

    def mgw(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return osmo_mgw.OsmoMgw(self, ip_address)

    def msc(self, hlr, mgcpgw, stp, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return osmo_msc.OsmoMsc(self, hlr, mgcpgw, stp, ip_address)

    def bsc(self, msc, mgw, stp, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return osmo_bsc.OsmoBsc(self, msc, mgw, stp, ip_address)

    def stp(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return osmo_stp.OsmoStp(self, ip_address)

    def bts(self, specifics=None):
        bts = bts_obj(self, self.reserved_resources.get(resource.R_BTS, specifics=specifics))
        bts.set_lac(self.lac())
        bts.set_rac(self.rac())
        bts.set_cellid(self.cellid())
        bts.set_bvci(self.bvci())
        self.register_for_cleanup(bts)
        return bts

    def modem(self, specifics=None):
        conf = self.reserved_resources.get(resource.R_MODEM, specifics=specifics)
        self.dbg('create Modem object', conf=conf)
        ms = modem.Modem(conf)
        self.register_for_cleanup(ms)
        return ms

    def modems(self, count):
        l = []
        for i in range(count):
            l.append(self.modem())
        return l

    def esme(self):
        esme_obj = esme.Esme(self.msisdn())
        self.register_for_cleanup(esme_obj)
        return esme_obj

    def msisdn(self):
        msisdn = self.resources_pool.next_msisdn(self)
        self.log('using MSISDN', msisdn)
        return msisdn

    def lac(self):
        lac = self.resources_pool.next_lac(self)
        self.log('using LAC', lac)
        return lac

    def rac(self):
        rac = self.resources_pool.next_rac(self)
        self.log('using RAC', rac)
        return rac

    def cellid(self):
        cellid = self.resources_pool.next_cellid(self)
        self.log('using CellId', cellid)
        return cellid

    def bvci(self):
        bvci = self.resources_pool.next_bvci(self)
        self.log('using BVCI', bvci)
        return bvci

    def poll(self):
        if self._processes:
            for process in self._processes:
                if process.terminated():
                    process.log_stdout_tail()
                    process.log_stderr_tail()
                    log.ctx(process)
                    raise log.Error('Process ended prematurely: %s' % process.name())

    def prompt(self, *msgs, **msg_details):
        'ask for user interaction. Do not use in tests that should run automatically!'
        if msg_details:
            msgs = list(msgs)
            msgs.append('{%s}' %
                        (', '.join(['%s=%r' % (k,v)
                                    for k,v in sorted(msg_details.items())])))
        msg = ' '.join(msgs) or 'Hit Enter to continue'
        self.log('prompt:', msg)
        sys.__stdout__.write('\n\n--- PROMPT ---\n')
        sys.__stdout__.write(msg)
        sys.__stdout__.write('\n')
        sys.__stdout__.flush()
        entered = util.input_polling('> ', event_loop.poll)
        self.log('prompt entered:', repr(entered))
        return entered

    def resource_status_str(self):
        return '\n'.join(('',
            'SUITE RUN: %s' % self.origin_id(),
            'ASKED FOR:', pprint.pformat(self._resource_requirements),
            'RESERVED COUNT:', pprint.pformat(self.reserved_resources.counts()),
            'RESOURCES STATE:', repr(self.reserved_resources)))

loaded_suite_definitions = {}

def load(suite_name):
    global loaded_suite_definitions

    suite = loaded_suite_definitions.get(suite_name)
    if suite is not None:
        return suite

    suites_dir = config.get_suites_dir()
    suite_dir = suites_dir.child(suite_name)
    if not suites_dir.exists(suite_name):
        raise RuntimeError('Suite not found: %r in %r' % (suite_name, suites_dir))
    if not suites_dir.isdir(suite_name):
        raise RuntimeError('Suite name found, but not a directory: %r' % (suite_dir))

    suite_def = SuiteDefinition(suite_dir)
    loaded_suite_definitions[suite_name] = suite_def
    return suite_def

def parse_suite_scenario_str(suite_scenario_str):
    tokens = suite_scenario_str.split(':')
    if len(tokens) > 2:
        raise RuntimeError('invalid combination string: %r' % suite_scenario_str)

    suite_name = tokens[0]
    if len(tokens) <= 1:
        scenario_names = []
    else:
        scenario_names = tokens[1].split('+')

    return suite_name, scenario_names

def load_suite_scenario_str(suite_scenario_str):
    suite_name, scenario_names = parse_suite_scenario_str(suite_scenario_str)
    suite = load(suite_name)
    scenarios = [config.get_scenario(scenario_name, resource.CONF_SCHEMA) for scenario_name in scenario_names]
    return (suite_scenario_str, suite, scenarios)

def bts_obj(suite_run, conf):
    bts_type = conf.get('type')
    log.dbg('create BTS object', type=bts_type)
    bts_class = resource.KNOWN_BTS_TYPES.get(bts_type)
    if bts_class is None:
        raise RuntimeError('No such BTS type is defined: %r' % bts_type)
    return bts_class(suite_run, conf)

# vim: expandtab tabstop=4 shiftwidth=4
