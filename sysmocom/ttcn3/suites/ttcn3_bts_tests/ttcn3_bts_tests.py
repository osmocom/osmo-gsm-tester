#!/usr/bin/env python3
import os

from osmo_gsm_tester.testenv import *
import testlib
tenv.test_import_modules_register_for_cleanup(testlib)
from testlib import run_ttcn3

ttcn3_test_execute="BTS_Tests.control"

hlr_dummy = tenv.hlr()
mgw_dummy = tenv.mgw()
stp_dummy = tenv.stp()
msc_dummy = tenv.msc(hlr_dummy, mgw_dummy, stp_dummy)
ggsn_dummy = tenv.ggsn()
sgsn_dummy = tenv.sgsn(hlr_dummy, ggsn_dummy)
bsc = tenv.bsc(msc_dummy, mgw_dummy, stp_dummy)
bts = tenv.bts()
osmocon = tenv.osmocon()

bts.set_num_trx(1)
bts.set_trx_phy_channel(0, 0, 'CCCH+SDCCH4')
bts.set_trx_phy_channel(0, 1, 'TCH/F')
bts.set_trx_phy_channel(0, 2, 'TCH/F')
bts.set_trx_phy_channel(0, 3, 'TCH/F_PDCH')
bts.set_trx_phy_channel(0, 4, 'TCH/F_TCH/H_PDCH')
bts.set_trx_phy_channel(0, 5, 'TCH/H')
bts.set_trx_phy_channel(0, 6, 'SDCCH8')
bts.set_trx_phy_channel(0, 7, 'PDCH')

print('Starting CNI')
hlr_dummy.start()
stp_dummy.start()
msc_dummy.start()
mgw_dummy.start()

nat_rsl_ip = tenv.ip_address().get('addr')
bsc.set_rsl_ip(nat_rsl_ip)
bsc.bts_add(bts)
sgsn_dummy.bts_add(bts)

bsc.start()
bts.start(keepalive=True)

print('Starting osmocon')
osmocon.start()

testdir = os.path.dirname(os.path.realpath(__file__))
run_ttcn3(tenv. test, testdir, bts, osmocon, nat_rsl_ip, ttcn3_test_execute)
