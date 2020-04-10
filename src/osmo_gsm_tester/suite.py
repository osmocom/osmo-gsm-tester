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
from . import config, log, util, resource, test
from .event_loop import MainLoop
from . import nitb_osmo, hlr_osmo, mgcpgw_osmo, mgw_osmo, msc_osmo, bsc_osmo, stp_osmo, ggsn_osmo, sgsn_osmo, esme, osmocon, ms_driver, iperf3, process
from . import run_node

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

    def __init__(self, trial, suite_scenario_str, suite_definition, scenarios=[]):
        super().__init__(log.C_TST, suite_scenario_str)
        self.start_timestamp = None
        self.duration = None
        self.reserved_resources = None
        self.objects_to_clean_up = None
        self.test_import_modules_to_clean_up = []
        self._resource_requirements = None
        self._resource_modifiers = None
        self._config = None
        self._processes = []
        self._run_dir = None
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

    def test_import_modules_register_for_cleanup(self, mod):
        '''
        Tests are required to call this API for any module loaded from its own
        lib subdir, because they are loaded in the global namespace. Otherwise
        later tests importing modules with the same name will re-use an already
        loaded module.
        '''
        if mod not in self.test_import_modules_to_clean_up:
            self.dbg('registering module %r for cleanup' % mod)
            self.test_import_modules_to_clean_up.append(mod)

    def test_import_modules_cleanup(self):
        while self.test_import_modules_to_clean_up:
            mod = self.test_import_modules_to_clean_up.pop()
            try:
                self.dbg('Cleaning up module %r' % mod)
                del sys.modules[mod.__name__]
                del mod
            except Exception:
                log.log_exn()

    def mark_start(self):
        self.start_timestamp = time.time()
        self.duration = 0
        self.status = SuiteRun.UNKNOWN

    def combined(self, conf_name, replicate_times=True):
        log.dbg(combining=conf_name)
        log.ctx(combining_scenarios=conf_name)
        combination = self.definition.conf.get(conf_name, {})
        if replicate_times:
            combination = config.replicate_times(combination)
        log.dbg(definition_conf=combination)
        for scenario in self.scenarios:
            log.ctx(combining_scenarios=conf_name, scenario=scenario.name())
            c = scenario.get(conf_name, {})
            if replicate_times:
                c = config.replicate_times(c)
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

    def resource_modifiers(self):
        if self._resource_modifiers is None:
            self._resource_modifiers = self.combined('modifiers')
        return self._resource_modifiers

    def config(self):
        if self._config is None:
            self._config = self.combined('config', False)
        return self._config

    def reserve_resources(self):
        if self.reserved_resources:
            raise RuntimeError('Attempt to reserve resources twice for a SuiteRun')
        self.log('reserving resources in', self.resources_pool.state_dir, '...')
        self.reserved_resources = self.resources_pool.reserve(self, self.resource_requirements(), self.resource_modifiers())

    def run_tests(self, names=None):
        suite_libdir = os.path.join(self.definition.suite_dir, 'lib')
        try:
            log.large_separator(self.trial.name(), self.name(), sublevel=2)
            self.mark_start()
            util.import_path_prepend(suite_libdir)
            MainLoop.register_poll_func(self.poll)
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
            MainLoop.unregister_poll_func(self.poll)
            self.test_import_modules_cleanup()
            util.import_path_remove(suite_libdir)
            self.duration = time.time() - self.start_timestamp

            passed, skipped, failed, errors = self.count_test_results()
            # if no tests ran, count it as failure
            if passed and not failed and not errors:
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
        errors = 0
        for t in self.tests:
            if t.status == test.Test.SKIP:
                skipped += 1
            elif t.status == test.Test.PASS:
                passed += 1
            elif t.status == test.Test.FAIL:
                failed += 1
            else: # error, could not run
                errors += 1
        return (passed, skipped, failed, errors)

    def remember_to_stop(self, process, respawn=False):
        '''Ask suite to monitor and manage lifecycle of the Process object. If a
        process managed by suite finishes before cleanup time, the current test
        will be marked as FAIL and end immediatelly. If respwan=True, then suite
        will respawn() the process instead.'''
        self._processes.insert(0, (process, respawn))

    def stop_processes(self):
        if len(self._processes) == 0:
            return
        strategy = process.ParallelTerminationStrategy()
        while self._processes:
            proc, _ = self._processes.pop()
            strategy.add_process(proc)
        strategy.terminate_all()

    def stop_process(self, process):
        'Remove process from monitored list and stop it'
        for proc_respawn in self._processes:
            proc, respawn = proc_respawn
            if proc == process:
                self._processes.remove(proc_respawn)
                proc.terminate()

    def free_resources(self):
        if self.reserved_resources is None:
            return
        self.reserved_resources.free()

    def ip_address(self, specifics=None):
        return self.reserved_resources.get(resource.R_IP_ADDRESS, specifics=specifics)

    def nitb(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return nitb_osmo.OsmoNitb(self, ip_address)

    def hlr(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return hlr_osmo.OsmoHlr(self, ip_address)

    def ggsn(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return ggsn_osmo.OsmoGgsn(self, ip_address)

    def sgsn(self, hlr, ggsn, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return sgsn_osmo.OsmoSgsn(self, hlr, ggsn, ip_address)

    def mgcpgw(self, ip_address=None, bts_ip=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return mgcpgw_osmo.OsmoMgcpgw(self, ip_address, bts_ip)

    def mgw(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return mgw_osmo.OsmoMgw(self, ip_address)

    def msc(self, hlr, mgcpgw, stp, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return msc_osmo.OsmoMsc(self, hlr, mgcpgw, stp, ip_address)

    def bsc(self, msc, mgw, stp, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return bsc_osmo.OsmoBsc(self, msc, mgw, stp, ip_address)

    def stp(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        return stp_osmo.OsmoStp(self, ip_address)

    def ms_driver(self):
        ms = ms_driver.MsDriver(self)
        self.register_for_cleanup(ms)
        return ms

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
        ms_type = conf.get('type')
        ms_class = resource.KNOWN_MS_TYPES.get(ms_type)
        if ms_class is None:
            raise RuntimeError('No such Modem type is defined: %r' % ms_type)
        self.dbg('create Modem object', conf=conf)
        ms = ms_class(self, conf)
        self.register_for_cleanup(ms)
        return ms

    def modems(self, count):
        l = []
        for i in range(count):
            l.append(self.modem())
        return l

    def all_resources(self, resource_func):
        """Returns all yielded resource."""
        l = []
        while True:
            try:
                l.append(resource_func())
            except resource.NoResourceExn:
                return l

    def esme(self):
        esme_obj = esme.Esme(self.msisdn())
        self.register_for_cleanup(esme_obj)
        return esme_obj

    def run_node(self, specifics=None):
        return run_node.RunNode.from_conf(self.reserved_resources.get(resource.R_RUN_NODE, specifics=specifics))

    def enb(self, specifics=None):
        enb = enb_obj(self, self.reserved_resources.get(resource.R_ENB, specifics=specifics))
        self.register_for_cleanup(enb)
        return enb

    def epc(self, run_node=None):
        if run_node is None:
            run_node = self.run_node()
        epc = epc_obj(self, run_node)
        self.register_for_cleanup(epc)
        return epc

    def osmocon(self, specifics=None):
        conf = self.reserved_resources.get(resource.R_OSMOCON, specifics=specifics)
        osmocon_obj = osmocon.Osmocon(self, conf=conf)
        self.register_for_cleanup(osmocon_obj)
        return osmocon_obj

    def iperf3srv(self, ip_address=None):
        if ip_address is None:
            ip_address = self.ip_address()
        iperf3srv_obj = iperf3.IPerf3Server(self, ip_address)
        return iperf3srv_obj

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
        for proc, respawn in self._processes:
            if proc.terminated():
                if respawn == True:
                    proc.respawn()
                else:
                    proc.log_stdout_tail()
                    proc.log_stderr_tail()
                    log.ctx(proc)
                    raise log.Error('Process ended prematurely: %s' % proc.name())

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
        entered = util.input_polling('> ', MainLoop.poll)
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

def enb_obj(suite_run, conf):
    enb_type = conf.get('type')
    log.dbg('create ENB object', type=enb_type)
    enb_class = resource.KNOWN_ENB_TYPES.get(enb_type)
    if enb_class is None:
        raise RuntimeError('No such ENB type is defined: %r' % enb_type)
    return enb_class(suite_run, conf)

def epc_obj(suite_run, run_node):
    values = dict(epc=config.get_defaults('epc'))
    config.overlay(values, dict(epc=suite_run.config().get('epc', {})))
    epc_type = values['epc'].get('type', None)
    if epc_type is None:
        raise RuntimeError('EPC type is not defined!')
    log.dbg('create EPC object', type=epc_type)
    epc_class = resource.KNOWN_EPC_TYPES.get(epc_type)
    if epc_class is None:
        raise RuntimeError('No such EPC type is defined: %r' % epc_type)
    return epc_class(suite_run, run_node)

# vim: expandtab tabstop=4 shiftwidth=4
