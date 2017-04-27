#!/usr/bin/env python3
import os
import _prep
from osmo_gsm_tester import log, suite, config

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
s = suite.SuiteRun(None, 'test_suite', s_def)
results = s.run_tests('hello_world.py')
print(str(results))

log.style_change(src=True)
#log.style_change(trace=True)
print('\n- a test with an error')
results = s.run_tests('test_error.py')
print(str(results))

print('\n- graceful exit.')
# vim: expandtab tabstop=4 shiftwidth=4
