#!/usr/bin/env python3
import os
import _prep
from osmo_gsm_tester import log, suite, config

#log.style_change(trace=True)

print('- non-existing suite dir')
assert(log.run_logging_exceptions(suite.load, 'does_not_exist') == None)

print('- no suite.conf')
assert(log.run_logging_exceptions(suite.load, os.path.join('suite_test', 'empty_dir')) == None)

print('- valid suite dir')
example_suite_dir = os.path.join('suite_test', 'test_suite')
s = suite.load(example_suite_dir)
assert(isinstance(s, suite.Suite))
print(config.tostr(s.conf))

print('- run hello world test')
s.run_tests_by_name('hello_world')

log.style_change(src=True)
#log.style_change(trace=True)
print('- a test with an error')
s.run_tests_by_name('test_error')

print('- graceful exit.')
# vim: expandtab tabstop=4 shiftwidth=4
