#!/usr/bin/env python3
from osmo_gsm_tester.test import *

print('use resources...')
nitb = suite.nitb()
bts = suite.bts()
ms_mo = suite.modem()
ms_mt = suite.modem()

print('start nitb and bts...')
nitb.add_bts(bts)
nitb.start()
sleep(.1)
assert nitb.running()
bts.start()

nitb.add_subscriber(ms_mo)
nitb.add_subscriber(ms_mt)

ms_mo.connect(nitb)
ms_mt.connect(nitb)
wait(nitb.subscriber_attached, ms_mo, ms_mt)

sms = ms_mo.sms_send(ms_mt.msisdn)
sleep(3)
wait(nitb.sms_received, sms)
