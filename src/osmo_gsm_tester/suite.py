# osmo_gsm_tester: test suite
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import sys
import time
from . import config, log, template, util, resource, schema, ofono_client, osmo_nitb
from . import test

class SuiteDefinition(log.Origin):
    '''A test suite reserves resources for a number of tests.
       Each test requires a specific number of modems, BTSs etc., which are
       reserved beforehand by a test suite. This way several test suites can be
       scheduled dynamically without resource conflicts arising halfway through
       the tests.'''

    CONF_FILENAME = 'suite.conf'

    CONF_SCHEMA = util.dict_add(
        {
            'defaults.timeout': schema.STR,
        },
        dict([('resources.%s' % k, t) for k,t in resource.WANT_SCHEMA.items()])
        )


    def __init__(self, suite_dir):
        self.set_log_category(log.C_CNF)
        self.suite_dir = suite_dir
        self.set_name(os.path.basename(self.suite_dir))
        self.read_conf()

    def read_conf(self):
        with self:
            self.dbg('reading %s' % SuiteDefinition.CONF_FILENAME)
            if not os.path.isdir(self.suite_dir):
                raise RuntimeError('No such directory: %r' % self.suite_dir)
            self.conf = config.read(os.path.join(self.suite_dir,
                                                 SuiteDefinition.CONF_FILENAME),
                                    SuiteDefinition.CONF_SCHEMA)
            self.load_tests()


    def load_tests(self):
        with self:
            self.tests = []
            for basename in sorted(os.listdir(self.suite_dir)):
                if not basename.endswith('.py'):
                    continue
                self.tests.append(Test(self, basename))

    def add_test(self, test):
        with self:
            if not isinstance(test, Test):
                raise ValueError('add_test(): pass a Test() instance, not %s' % type(test))
            if test.suite is None:
                test.suite = self
            if test.suite is not self:
                raise ValueError('add_test(): test already belongs to another suite')
            self.tests.append(test)



class Test(log.Origin):

    def __init__(self, suite, test_basename):
        self.suite = suite
        self.basename = test_basename
        self.path = os.path.join(self.suite.suite_dir, self.basename)
        super().__init__(self.path)
        self.set_name(self.basename)
        self.set_log_category(log.C_TST)

    def run(self, suite_run):
        assert self.suite is suite_run.definition
        with self:
            test.setup(suite_run, self, ofono_client)
            success = False
            try:
                self.log('START')
                with self.redirect_stdout():
                    util.run_python_file('%s.%s' % (self.suite.name(), self.name()),
                                         self.path)
                    success = True
            except resource.NoResourceExn:
                self.err('Current resource state:\n', repr(reserved_resources))
                raise
            finally:
                if success:
                    self.log('PASS')
                else:
                    self.log('FAIL')

    def name(self):
        l = log.get_line_for_src(self.path)
        if l is not None:
            return '%s:%s' % (self._name, l)
        return super().name()

class SuiteRun(log.Origin):

    trial = None
    resources_pool = None
    reserved_resources = None
    _resource_requirements = None
    _config = None
    _processes = None

    def __init__(self, current_trial, suite_definition, scenarios=[]):
        self.trial = current_trial
        self.definition = suite_definition
        self.scenarios = scenarios
        self.set_name(suite_definition.name())
        self.set_log_category(log.C_TST)
        self.resources_pool = resource.ResourcesPool()

    def combined(self, conf_name):
        combination = self.definition.conf.get(conf_name) or {}
        for scenario in self.scenarios:
            c = scenario.get(conf_name)
            if c is None:
                continue
            config.combine(combination, c)
        return combination

    def resource_requirements(self):
        if self._resource_requirements is None:
            self._resource_requirements = self.combined('resources')
        return self._resource_requirements

    def config(self):
        if self._config is None:
            self._config = self.combined('config')
        return self._config

    class Results:
        def __init__(self):
            self.passed = []
            self.failed = []
            self.all_passed = None

        def add_pass(self, test):
            self.passed.append(test)

        def add_fail(self, test):
            self.failed.append(test)

        def conclude(self):
            self.all_passed = bool(self.passed) and not bool(self.failed)
            return self

        def __str__(self):
            if self.failed:
                return 'FAIL: %d of %d tests failed:\n  %s' % (
                       len(self.failed),
                       len(self.failed) + len(self.passed),
                       '\n  '.join([t.name() for t in self.failed]))
            if not self.passed:
                return 'no tests were run.'
            return 'pass: all %d tests passed.' % len(self.passed)

    def reserve_resources(self):
        if self.reserved_resources:
            raise RuntimeError('Attempt to reserve resources twice for a SuiteRun')
        self.log('reserving resources...')
        with self:
            self.reserved_resources = self.resources_pool.reserve(self, self.resource_requirements())

    def run_tests(self, names=None):
        if not self.reserved_resources:
            self.reserve_resources()
        results = SuiteRun.Results()
        for test in self.definition.tests:
            if names and not test.name() in names:
                continue
            self._run_test(test, results)
        self.stop_processes()
        return results.conclude()

    def _run_test(self, test, results):
        try:
            with self:
                test.run(self)
            results.add_pass(test)
        except:
            results.add_fail(test)
            self.log_exn()

    def remember_to_stop(self, process):
        if self._processes is None:
            self._processes = []
        self._processes.append(process)

    def stop_processes(self):
        if not self._processes:
            return
        for process in self._processes:
            process.terminate()

    def nitb_iface(self):
        return self.reserved_resources.get(resource.R_NITB_IFACE)

    def nitb(self, nitb_iface=None):
        if nitb_iface is None:
            nitb_iface = self.nitb_iface()
        return osmo_nitb.OsmoNitb(self, nitb_iface)

    def bts(self):
        return bts_obj(self, self.reserved_resources.get(resource.R_BTS))

    def modem(self):
        return modem_obj(self.reserved_resources.get(resource.R_MODEM))

    def msisdn(self):
        msisdn = self.resources_pool.next_msisdn(self.origin)
        self.log('using MSISDN', msisdn)
        return msisdn

    def _wait(self, condition, condition_args, condition_kwargs, timeout, timestep):
        if not timeout or timeout < 0:
            raise RuntimeError('wait() *must* time out at some point. timeout=%r' % timeout)
        if timestep < 0.1:
            timestep = 0.1

        started = time.time()
        while True:
            self.poll()
            if condition(*condition_args, **condition_kwargs):
                return True
            waited = time.time() - started
            if waited > timeout:
                return False
            time.sleep(timestep)

    def wait(self, condition, *condition_args, timeout=300, timestep=1, **condition_kwargs):
        if not self._wait(condition, condition_args, condition_kwargs, timeout, timestep):
            raise RuntimeError('Timeout expired')

    def sleep(self, seconds):
        assert seconds > 0.
        self._wait(lambda: False, [], {}, timeout=seconds, timestep=min(seconds, 1))

    def poll(self):
        ofono_client.poll()
        if self._processes:
            for process in self._processes:
                if process.terminated():
                    process.log_stdout_tail()
                    process.log_stderr_tail()
                    process.raise_exn('Process ended prematurely')

    def prompt(self, *msgs, **msg_details):
        'ask for user interaction. Do not use in tests that should run automatically!'
        if msg_details:
            msgs = list(msgs)
            msgs.append('{%s}' %
                        (', '.join(['%s=%r' % (k,v)
                                    for k,v in sorted(msg_details.items())])))
        msg = ' '.join(msgs) or 'Hit Enter to continue'
        self.log('prompt:', msg)
        sys.__stdout__.write(msg)
        sys.__stdout__.write('\n> ')
        sys.__stdout__.flush()
        entered = util.input_polling(self.poll)
        self.log('prompt entered:', entered)
        return entered


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
    scenarios = [config.get_scenario(scenario_name) for scenario_name in scenario_names]
    return (suite, scenarios)

def bts_obj(suite_run, conf):
    bts_type = conf.get('type')
    log.dbg(None, None, 'create BTS object', type=bts_type)
    bts_class = resource.KNOWN_BTS_TYPES.get(bts_type)
    if bts_class is None:
        raise RuntimeError('No such BTS type is defined: %r' % bts_type)
    return bts_class(suite_run, conf)

def modem_obj(conf):
    log.dbg(None, None, 'create Modem object', conf=conf)
    return ofono_client.Modem(conf)

# vim: expandtab tabstop=4 shiftwidth=4
