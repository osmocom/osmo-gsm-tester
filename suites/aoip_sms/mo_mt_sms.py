#!/usr/bin/env python3
from osmo_gsm_tester.test import *

hlr = suite.hlr()
bts = suite.bts()
mgcpgw = suite.mgcpgw(bts_ip=bts.remote_addr())
msc = suite.msc(hlr, mgcpgw)
bsc = suite.bsc(msc)
ms_mo = suite.modem()
ms_mt = suite.modem()

hlr.start()
msc.start()
mgcpgw.start()

bsc.bts_add(bts)
bsc.start()

bts.start()

hlr.subscriber_add(ms_mo)
hlr.subscriber_add(ms_mt)

ms_mo.connect(bsc)
ms_mt.connect(bsc)
wait(msc.subscriber_attached, ms_mo, ms_mt)

sms = ms_mo.sms_send(ms_mt.msisdn)
wait(ms_mt.sms_was_received, sms)
