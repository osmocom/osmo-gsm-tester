#!/usr/bin/env python3
from osmo_gsm_tester.test import *

print('use resources...')
nitb = suite.nitb()
bts = suite.bts()
ms_mo = suite.modem()
ms_mt = suite.modem()

print('start nitb and bts...')
nitb.bts_add(bts)
nitb.start()
sleep(1)
assert nitb.running()
bts.start()

nitb.subscriber_add(ms_mo)
nitb.subscriber_add(ms_mt)

ms_mo.connect(nitb)
ms_mt.connect(nitb)
print(ms_mo.properties())
print(ms_mt.properties())
wait(nitb.subscriber_attached, ms_mo, ms_mt)

sms = ms_mo.sms_send(ms_mt.msisdn)
wait(ms_mt.sms_was_received, sms)
