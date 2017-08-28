#!/usr/bin/env python3
from osmo_gsm_tester.test import *

nitb = suite.nitb()
arfcn = suite.reserve_arfcn(band='GSM-1900')
bts = suite.bts(arfcn)
ms = suite.modem()

print('start nitb and bts...')
nitb.bts_add(bts)
nitb.start()
bts.start()

nitb.subscriber_add(ms)

ms.connect(nitb.mcc_mnc())

ms.log_info()

print('waiting for modems to attach...')
wait(ms.is_connected, nitb.mcc_mnc())
wait(nitb.subscriber_attached, ms)
