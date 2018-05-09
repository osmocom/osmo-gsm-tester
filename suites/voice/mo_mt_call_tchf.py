#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

import testlib
suite.test_import_modules_register_for_cleanup(testlib)
from testlib import call_test_setup_run

def my_bts_setup(bts):
    bts.set_num_trx(1)
    bts.set_trx_phy_channel(0, 0, 'CCCH+SDCCH4')
    bts.set_trx_phy_channel(0, 1, 'SDCCH8')
    bts.set_trx_phy_channel(0, 2, 'TCH/F')
    bts.set_trx_phy_channel(0, 3, 'TCH/F')
    bts.set_trx_phy_channel(0, 4, 'TCH/F')
    bts.set_trx_phy_channel(0, 5, 'TCH/F')
    bts.set_trx_phy_channel(0, 6, 'TCH/F')
    bts.set_trx_phy_channel(0, 7, 'TCH/F')

call_test_setup_run(bts_setup_cb=my_bts_setup)
