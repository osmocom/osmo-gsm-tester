#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

import testlib
tenv.test_import_modules_register_for_cleanup(testlib)
from testlib import setup_run_iperf3_test_parallel

setup_run_iperf3_test_parallel(4)
