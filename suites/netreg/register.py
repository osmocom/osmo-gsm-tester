#!/usr/bin/env python3
from osmo_gsm_tester.test import *

print('use resources...')
nitb = suite.nitb()
bts = suite.bts()
ms = suite.modem()

print('start nitb and bts...')
nitb.bts_add(bts)
nitb.start()
bts.start()

nitb.subscriber_add(ms)

ms.connect(nitb.mcc_mnc())

print(ms.info())

wait(ms.is_connected, nitb.mcc_mnc())
wait(nitb.subscriber_attached, ms)
