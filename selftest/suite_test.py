#!/usr/bin/env python3
import os
import _prep
from osmo_gsm_tester import log, suite, config, report

config.ENV_CONF = './suite_test'

#log.style_change(trace=True)

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
trial = log.Origin(log.C_TST, 'trial')
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
trial = log.Origin(log.C_TST, 'trial')
scenario = config.Scenario('foo', 'bar')
scenario['resources'] = { 'bts': [{'type': 'sysmo'}] }
s = suite.SuiteRun(trial, 'test_suite', s_def, [scenario])
results = s.run_tests('hello_world.py')
print(report.suite_to_text(s))

print('- test with scenario')
trial = log.Origin(log.C_TST, 'trial')
scenario = config.Scenario('foo', 'bar')
scenario['resources'] = { 'bts': [{ 'times': '2', 'type': 'osmo-bts-trx', 'trx_list': [{'nominal_power': '10'}, {'nominal_power': '12'}]}, {'type': 'sysmo'}] }
s = suite.SuiteRun(trial, 'test_suite', s_def, [scenario])
results = s.run_tests('hello_world.py')
print(report.suite_to_text(s))

print('\n- graceful exit.')
# vim: expandtab tabstop=4 shiftwidth=4
