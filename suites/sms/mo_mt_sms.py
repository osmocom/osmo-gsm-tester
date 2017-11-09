#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

nitb = suite.nitb()
bts = suite.bts()
ms_mo = suite.modem()
ms_mt = suite.modem()

print('start nitb and bts...')
nitb.bts_add(bts)
nitb.start()
bts.start()

nitb.subscriber_add(ms_mo)
nitb.subscriber_add(ms_mt)

ms_mo.connect(nitb.mcc_mnc())
ms_mt.connect(nitb.mcc_mnc())

ms_mo.log_info()
ms_mt.log_info()

print('waiting for modems to attach...')
wait(ms_mo.is_connected, nitb.mcc_mnc())
wait(ms_mt.is_connected, nitb.mcc_mnc())
wait(nitb.subscriber_attached, ms_mo, ms_mt)

sms = ms_mo.sms_send(ms_mt)
wait(ms_mt.sms_was_received, sms)
