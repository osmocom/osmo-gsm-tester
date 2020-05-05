#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

import testlib
tenv.test_import_modules_register_for_cleanup(testlib)
from testlib import encryption_test_setup_run

encryption_test_setup_run(True, 'a5_1')
