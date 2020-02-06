#!/usr/bin/env python3
import os

from osmo_gsm_tester.testenv import *
import testlib
suite.test_import_modules_register_for_cleanup(testlib)
from testlib import run_ttcn3

ttcn3_test_execute="BTS_Tests_perf.TC_pespin"
ttcn3_test_extra_module_params="BTS_Tests_perf.mp_wait_time := 11.0"

hlr_dummy = suite.hlr()
mgw_dummy = suite.mgw()
stp_dummy = suite.stp()
msc_dummy = suite.msc(hlr_dummy, mgw_dummy, stp_dummy)
ggsn_dummy = suite.ggsn()
sgsn_dummy = suite.sgsn(hlr_dummy, ggsn_dummy)
bsc = suite.bsc(msc_dummy, mgw_dummy, stp_dummy)
bts = suite.bts()
osmocon = suite.osmocon()

bts.set_num_trx(1)
bts.set_trx_phy_channel(0, 0, 'CCCH+SDCCH4')
bts.set_trx_phy_channel(0, 1, 'TCH/H')
bts.set_trx_phy_channel(0, 2, 'TCH/H')
bts.set_trx_phy_channel(0, 3, 'TCH/H')
bts.set_trx_phy_channel(0, 4, 'TCH/H')
bts.set_trx_phy_channel(0, 5, 'TCH/H')
bts.set_trx_phy_channel(0, 6, 'TCH/H')
bts.set_trx_phy_channel(0, 7, 'TCH/H')

print('Starting CNI')
hlr_dummy.start()
stp_dummy.start()
msc_dummy.start()
mgw_dummy.start()

nat_rsl_ip = suite.ip_address().get('addr')
bsc.set_rsl_ip(nat_rsl_ip)
bsc.bts_add(bts)
sgsn_dummy.bts_add(bts)

bsc.start()
bts.start(keepalive=True)

print('Starting osmocon')
osmocon.start()

testdir = os.path.dirname(os.path.realpath(__file__))
run_ttcn3(suite, test, testdir, bts, osmocon, nat_rsl_ip, ttcn3_test_execute, ttcn3_test_extra_module_params)
