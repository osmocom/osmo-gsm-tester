#!/usr/bin/env python3
from osmo_gsm_tester.test import *

print('I am %r / %r' % (suite.name(), test.name()))

test.set_fail('EpicFail', 'This failure is expected')
