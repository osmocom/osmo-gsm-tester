#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

hlr = suite.hlr()
bts = suite.bts()
mgcpgw = suite.mgcpgw(bts_ip=bts.remote_addr())
mgw_bsc = suite.mgw()
stp = suite.stp()
msc = suite.msc(hlr, mgcpgw, stp)
bsc = suite.bsc(msc, mgw_bsc, stp)
ms = suite.modem()

print('start network...')
msc.set_authentication(True)
msc.set_encryption('a5_1')
bsc.set_encryption('a5_1')
hlr.start()
stp.start()
msc.start()
mgcpgw.start()
mgw_bsc.start()
bsc.bts_add(bts)
bsc.start()
bts.start()
wait(bsc.bts_is_connected, bts)

ms.log_info()
good_ki = ms.ki()
bad_ki = ("%1X" % (int(good_ki[0], 16) ^ 0x01)) + good_ki[1:]

print('KI changed: ' + good_ki + " => " + bad_ki)
ms.set_ki(bad_ki)
hlr.subscriber_add(ms)
print('Attempt connection with wrong KI...')
ms.connect(msc.mcc_mnc())

sleep(40) # TODO: read pcap or CTRL interface and look for Rejected? (gsm_a.dtap.msg_mm_type == 0x04)
print('Asserting modem did not register')
# FIXME: this can fail because ofono qmi signals registered before being accepted by network. See OS#2458
# assert not ms.is_connected(msc.mcc_mnc())
assert not msc.subscriber_attached(ms)

hlr.subscriber_delete(ms)
print('KI changed: ' + bad_ki + " => " + good_ki)
ms.set_ki(good_ki)
hlr.subscriber_add(ms, ms.msisdn)
print('Attempt connection with correct KI...')
ms.connect(msc.mcc_mnc())
wait(ms.is_connected, msc.mcc_mnc())
wait(msc.subscriber_attached, ms)
