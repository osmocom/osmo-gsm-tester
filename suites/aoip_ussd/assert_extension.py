#!/usr/bin/env python3
from osmo_gsm_tester.test import *

USSD_COMMAND_GET_EXTENSION = '*#100#'

hlr = suite.hlr()
bts = suite.bts()
mgcpgw = suite.mgcpgw(bts_ip=bts.remote_addr())
msc = suite.msc(hlr, mgcpgw)
bsc = suite.bsc(msc)
stp = suite.stp()
ms = suite.modem()

hlr.start()
stp.start()
msc.start()
mgcpgw.start()

bsc.bts_add(bts)
bsc.start()

bts.start()

hlr.subscriber_add(ms)

ms.connect(msc.mcc_mnc())

ms.log_info()

print('waiting for modems to attach...')
wait(ms.is_connected, msc.mcc_mnc())
wait(msc.subscriber_attached, ms)

print('Sending ussd code %s' % USSD_COMMAND_GET_EXTENSION)
response = ms.ussd_send(USSD_COMMAND_GET_EXTENSION)
assert ' ' + ms.msisdn + '\r' in response
