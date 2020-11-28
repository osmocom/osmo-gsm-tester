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
from . import config
from . import log
from . import util
from . import schema
from . import resource
from . import scenario
from . import test

class SuiteDefinition(log.Origin):
    '''A test suite reserves resources for a number of tests.
       Each test requires a specific number of modems, BTSs etc., which are
       reserved beforehand by a test suite. This way several test suites can be
       scheduled dynamically without resource conflicts arising halfway through
       the tests.'''

    CONF_FILENAME = 'suite.conf'

    def __init__(self, suite_dir):
        self._suite_name = os.path.basename(suite_dir)
        super().__init__(log.C_CNF, self._suite_name)
        self.suite_dir = suite_dir
        self.conf = None
        self._schema = None
        self.test_basenames = []
        self.load_test_basenames()
        self.read_conf()

    def read_conf(self):
        self.dbg('reading %s' % SuiteDefinition.CONF_FILENAME)
        if not os.path.isdir(self.suite_dir):
            raise RuntimeError('No such directory: %r' % self.suite_dir)
        self.conf = config.read(os.path.join(self.suite_dir,
                                             SuiteDefinition.CONF_FILENAME))
        # Drop schema part since it's dynamically defining content, makes no sense to validate it.
        self._schema = self.conf.pop('schema', {})
        # Add per-test 'timeout' attribute:
        d = {t.rstrip('.py'):{'timeout': schema.DURATION} for t in self.test_basenames}
        schema.combine(self._schema, d)
        # Convert config file format to proper schema format and register it:
        sdef = schema.config_to_schema_def(self._schema, "%s." % self._suite_name)
        schema.register_config_schema('suite', sdef)
        # Finally validate the file:
        schema.validate(self.conf, schema.get_all_schema())

    def load_test_basenames(self):
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
        self.duration = 0
        self.reserved_resources = None
        self._resource_requirements = None
        self._resource_modifiers = None
        self._config = None
        self._run_dir = None
        self._trial = trial
        self.definition = suite_definition
        self.scenarios = scenarios
        self.resources_pool = resource.ResourcesPool()
        self.status = SuiteRun.UNKNOWN
        self.load_tests()

    def suite_name(self):
        'Return name of suite without scenarios'
        return self.definition.name()

    def trial(self):
        return self._trial

    def load_tests(self):
        self.tests = []
        for test_basename in self.definition.test_basenames:
            test_specific_config = self.config_suite_specific().get(test_basename.rstrip('.py'), {})
            self.tests.append(test.Test(self, test_basename, test_specific_config))

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
        for sc in self.scenarios:
            log.ctx(combining_scenarios=conf_name, scenario=sc.name())
            c = sc.get(conf_name, {})
            if replicate_times:
                c = config.replicate_times(c)
            log.dbg(scenario=sc.name(), conf=c)
            if c is None:
                continue
            schema.combine(combination, c)
        return combination

    def get_run_dir(self):
        if self._run_dir is None:
            self._run_dir = util.Dir(self._trial.get_run_dir().new_dir(self.name()))
        return self._run_dir

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

    def config_suite_specific(self):
        return self.config().get('suite', {}).get(self.suite_name(), {})

    def resource_pool(self):
        return self.resources_pool

    def reserve_resources(self):
        if self.reserved_resources:
            raise RuntimeError('Attempt to reserve resources twice for a SuiteRun')
        self.log('reserving resources in', self.resources_pool.state_dir, '...')
        self.reserved_resources = self.resources_pool.reserve(self, self.resource_requirements(), self.resource_modifiers())
        # short summary of labels
        self.log('RESERVED RESOURCES for ' + self.suite_name() + ':\n' + self.reserved_resources.summary_str())

    def get_reserved_resource(self, resource_class_str, specifics):
        return self.reserved_resources.get(resource_class_str, specifics=specifics)

    def run_tests(self, names=None):
        suite_libdir = os.path.join(self.definition.suite_dir, 'lib')
        try:
            log.large_separator(self._trial.name(), self.name(), sublevel=2)
            self.mark_start()
            util.import_path_prepend(suite_libdir)
            if not self.reserved_resources:
                self.reserve_resources()
            for t in self.tests:
                if names and not t.name() in names:
                    t.set_skip()
                    continue
                self.current_test = t
                t.run()
        except Exception:
            log.log_exn()
        except BaseException as e:
            # when the program is aborted by a signal (like Ctrl-C), escalate to abort all.
            self.err('SUITE RUN ABORTED: %s' % type(e).__name__)
            raise
        finally:
            self.free_resources()
            util.import_path_remove(suite_libdir)
            self.duration = time.time() - self.start_timestamp

            self.determine_status()

            log.large_separator(self._trial.name(), self.name(), self.status, sublevel=2, space_above=False)

    def passed(self):
        return self.status == SuiteRun.PASS

    def determine_status(self):
        passed, skipped, failed, errors = self.count_test_results()
        # if no tests ran, count it as failure
        if passed and not failed and not errors:
            self.status = SuiteRun.PASS
        else:
            self.status = SuiteRun.FAIL

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

    def free_resources(self):
        if self.reserved_resources is None:
            return
        self.reserved_resources.free()

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

    suites_dirs = config.get_suites_dirs()
    suite_dir = None
    found = False
    for d in suites_dirs:
        suite_dir = d.child(suite_name)
        if d.exists(suite_name) and d.isdir(suite_name):
            found = True
            break
    if not found:
        raise RuntimeError('Suite not found: %r in %r' % (suite_name, suites_dirs))

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
    scenarios = [scenario.get_scenario(scenario_name, schema.get_all_schema()) for scenario_name in scenario_names]
    return (suite_scenario_str, suite, scenarios)

# vim: expandtab tabstop=4 shiftwidth=4
