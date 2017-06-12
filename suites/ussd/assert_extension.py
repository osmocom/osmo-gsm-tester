#!/usr/bin/env python3
from osmo_gsm_tester.test import *

USSD_COMMAND_GET_EXTENSION = '*#100#'

nitb = suite.nitb()
bts = suite.bts()
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

print('Sending ussd code %s' % USSD_COMMAND_GET_EXTENSION)
response = ms.ussd_send(USSD_COMMAND_GET_EXTENSION)
assert ' ' + ms.msisdn + '\r' in response
