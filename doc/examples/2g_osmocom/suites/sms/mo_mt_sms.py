#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

hlr = suite.hlr()
bts = suite.bts()
mgw_msc = suite.mgw()
mgw_bsc = suite.mgw()
stp = suite.stp()
msc = suite.msc(hlr, mgw_msc, stp)
bsc = suite.bsc(msc, mgw_bsc, stp)
ms_mo = suite.modem()
ms_mt = suite.modem()

hlr.start()
stp.start()
msc.start()
mgw_msc.start()
mgw_bsc.start()

bsc.bts_add(bts)
bsc.start()

bts.start()
wait(bsc.bts_is_connected, bts)

hlr.subscriber_add(ms_mo)
hlr.subscriber_add(ms_mt)

ms_mo.connect(msc.mcc_mnc())
ms_mt.connect(msc.mcc_mnc())

ms_mo.log_info()
ms_mt.log_info()

print('waiting for modems to attach...')
wait(ms_mo.is_connected, msc.mcc_mnc())
wait(ms_mt.is_connected, msc.mcc_mnc())
wait(msc.subscriber_attached, ms_mo, ms_mt)

sms = ms_mo.sms_send(ms_mt)
wait(ms_mt.sms_was_received, sms)
