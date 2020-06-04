#!/usr/bin/env python3
import os
import sys
import _prep
import shutil
from osmo_gsm_tester.core import log
from osmo_gsm_tester.core import config
from osmo_gsm_tester.core import util
from osmo_gsm_tester.core import report
from osmo_gsm_tester.core import scenario
from osmo_gsm_tester.core import suite
from osmo_gsm_tester.core.schema import generate_schemas, get_all_schema

config.override_conf = os.path.join(os.path.dirname(sys.argv[0]), 'paths.conf')

example_trial_dir = os.path.join('test_trial_tmp')

class FakeTrial(log.Origin):
    def __init__(self):
        super().__init__(log.C_TST, 'trial')
        self.dir = util.Dir(example_trial_dir)
        self._run_dir = None

    def get_run_dir(self):
        if self._run_dir is not None:
            return self._run_dir
        self._run_dir = util.Dir(self.dir.new_child('test_run'))
        self._run_dir.mkdir()
        return self._run_dir

#log.style_change(trace=True)

# Generate supported schemas dynamically from objects:
generate_schemas()

print('- non-existing suite dir')
assert(log.run_logging_exceptions(suite.load, 'does_not_exist') == None)

print('- no suite.conf')
assert(log.run_logging_exceptions(suite.load, 'empty_dir') == None)

print('- valid suite dir')
example_suite_dir = os.path.join('test_suite')
s_def = suite.load(example_suite_dir)
assert(isinstance(s_def, suite.SuiteDefinition))
print(config.tostr(s_def.conf))

print('- run hello world test')
trial = FakeTrial()
s = suite.SuiteRun(trial, 'test_suite', s_def)
results = s.run_tests('hello_world.py')
print(report.suite_to_text(s))

log.style_change(src=True)
#log.style_change(trace=True)
print('\n- a test with an error')
results = s.run_tests('test_error.py')
output = report.suite_to_text(s)
print(output)

print('\n- a test with a failure')
results = s.run_tests('test_fail.py')
output = report.suite_to_text(s)
print(output)

print('\n- a test with a raised failure')
results = s.run_tests('test_fail_raise.py')
output = report.suite_to_text(s)
print(output)

print('- test with half empty scenario')
trial = FakeTrial()
sc = scenario.Scenario('foo', 'bar')
sc['resources'] = { 'bts': [{'type': 'osmo-bts-trx'}] }
s = suite.SuiteRun(trial, 'test_suite', s_def, [sc])
results = s.run_tests('hello_world.py')
print(report.suite_to_text(s))

print('- test with scenario')
trial = FakeTrial()
sc = scenario.Scenario('foo', 'bar')
sc['resources'] = { 'bts': [{ 'times': '2', 'type': 'osmo-bts-trx', 'trx_list': [{'nominal_power': '10'}, {'nominal_power': '12'}]}, {'type': 'sysmo'}] }
s = suite.SuiteRun(trial, 'test_suite', s_def, [sc])
results = s.run_tests('hello_world.py')
print(report.suite_to_text(s))

print('- test with scenario and modifiers')
trial = FakeTrial()
sc = scenario.Scenario('foo', 'bar')
sc['resources'] = { 'bts': [{ 'times': '2', 'type': 'osmo-bts-trx', 'trx_list': [{'nominal_power': '10'}, {'nominal_power': '12'}]}, {'type': 'sysmo'}] }
sc['modifiers'] = { 'bts': [{ 'times': '2', 'trx_list': [{'nominal_power': '20'}, {'nominal_power': '20'}]}, {'type': 'sysmo'}] }
s = suite.SuiteRun(trial, 'test_suite', s_def, [sc])
s.reserve_resources()
print(repr(s.reserved_resources))
results = s.run_tests('hello_world.py')
print(report.suite_to_text(s))

print('- test with suite-specific config')
trial = FakeTrial()
sc = scenario.Scenario('foo', 'bar')
sc['config'] = {'suite': {s.name(): { 'some_suite_global_param': 'heyho', 'test_suite_params': {'one_bool_parameter': 'true', 'second_list_parameter': ['23', '45']}}}}
s = suite.SuiteRun(trial, 'test_suite', s_def, [sc])
s.reserve_resources()
print(repr(s.reserved_resources))
results = s.run_tests('test_suite_params.py')
print(report.suite_to_text(s))

print('- test with template overlay')
trial = FakeTrial()
s_def = suite.load('suiteC')
s = suite.SuiteRun(trial, 'suiteC', s_def)
results = s.run_tests('test_template_overlay.py')
print(report.suite_to_text(s))

print('\n- graceful exit.')
#deleting generated tmp trial dir:
shutil.rmtree(example_trial_dir, ignore_errors=True)

# vim: expandtab tabstop=4 shiftwidth=4
