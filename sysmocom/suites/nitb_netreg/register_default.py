#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

print('use resources...')
nitb = tenv.nitb()
bts = tenv.bts()
ms = tenv.modem()

print('start nitb and bts...')
nitb.bts_add(bts)
nitb.start()
bts.start()
wait(nitb.bts_is_connected, bts)

nitb.subscriber_add(ms)

ms.connect()

print(ms.info())

wait(ms.is_registered)
wait(nitb.subscriber_attached, ms)
