#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

USSD_COMMAND_GET_EXTENSION = '*#100#'

nitb = tenv.nitb()
bts = tenv.bts()
ms = tenv.modem()

print('start nitb and bts...')
nitb.bts_add(bts)
nitb.start()
bts.start()
wait(nitb.bts_is_connected, bts)

nitb.subscriber_add(ms)

ms.connect(nitb.mcc_mnc())
ms.log_info()

print('waiting for modems to attach...')
wait(ms.is_registered, nitb.mcc_mnc())
wait(nitb.subscriber_attached, ms)

# ofono (qmi) currently changes state to 'registered' jut after sending
# 'Location Update Request', but before receiving 'Location Updating Accept'.
# Which means we can reach lines below and send USSD code while still not being
# attached, which will then fail. See OsmoGsmTester #2239 for more detailed
# information.
# Until we find an ofono fix or a better way to workaround this, let's just
# sleep for a while in order to receive the 'Location Updating Accept' message
# before attemting to send the USSD.
sleep(10)

print('Sending ussd code %s' % USSD_COMMAND_GET_EXTENSION)
response = ms.ussd_send(USSD_COMMAND_GET_EXTENSION)
assert ' ' + ms.msisdn() + '\r' in response
