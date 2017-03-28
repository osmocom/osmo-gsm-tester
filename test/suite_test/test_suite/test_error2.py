#!/usr/bin/env python3

from osmo_gsm_tester import test
from osmo_gsm_tester.test import resources

print('I am %r / %r' % (test.suite.name(), test.test.name()))

assert(False)
