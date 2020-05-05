#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

import testlib
tenv.test_import_modules_register_for_cleanup(testlib)
from testlib import test_mo_mt_call

test_mo_mt_call(True, True)
