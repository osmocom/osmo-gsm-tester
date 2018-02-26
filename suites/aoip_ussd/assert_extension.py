#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

USSD_COMMAND_GET_EXTENSION = '*#100#'

hlr = suite.hlr()
bts = suite.bts()
mgw_msc = suite.mgw()
mgw_bsc = suite.mgw()
stp = suite.stp()
msc = suite.msc(hlr, mgw_msc, stp)
bsc = suite.bsc(msc, mgw_bsc, stp)
ms = suite.modem()

hlr.start()
stp.start()
msc.start()
mgw_msc.start()
mgw_bsc.start()

bsc.bts_add(bts)
bsc.start()

bts.start()
wait(bsc.bts_is_connected, bts)

hlr.subscriber_add(ms)

ms.connect(msc.mcc_mnc())

ms.log_info()

print('waiting for modems to attach...')
wait(ms.is_connected, msc.mcc_mnc())
wait(msc.subscriber_attached, ms)

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
assert ' ' + ms.msisdn + '\r' in response
