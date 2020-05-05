#!/usr/bin/env python3

# This test checks following use-cases:
# * SMPP interface of SMSC accepts SMPP clients (ESMEs) with password previously
#   defined in its configuration file.
# * When SMS is sent in 'transaction' mode, ESME can send an SMS to an already registered MS.
# * When SMS is sent in 'transaction' mode, ESME fails to send an SMS to non registered MS.

from osmo_gsm_tester.testenv import *

SMPP_ESME_RINVDSTADR = 0x0000000B

hlr = tenv.hlr()
bts = tenv.bts()
mgw_msc = tenv.mgw()
mgw_bsc = tenv.mgw()
stp = tenv.stp()
msc = tenv.msc(hlr, mgw_msc, stp)
bsc = tenv.bsc(msc, mgw_bsc, stp)
bsc.bts_add(bts)

ms = tenv.modem()
esme = tenv.esme()
msc.smsc.esme_add(esme)

hlr.start()
stp.start()
msc.start()
mgw_msc.start()
mgw_bsc.start()
bsc.start()
bts.start()
wait(bsc.bts_is_connected, bts)

esme.connect()
hlr.subscriber_add(ms)
ms.connect(msc.mcc_mnc())

ms.log_info()
print('waiting for modem to attach...')
wait(ms.is_connected, msc.mcc_mnc())
wait(msc.subscriber_attached, ms)

print('sending first sms...')
msg = Sms(esme.msisdn, ms.msisdn, 'smpp send message')
esme.sms_send(msg, esme.MSGMODE_TRANSACTION)
wait(ms.sms_was_received, msg)

print('sending second sms (unicode chars not in gsm aplhabet)...')
msg = Sms(esme.msisdn, ms.msisdn, 'chars:[кизаçйж]')
esme.sms_send(msg, esme.MSGMODE_TRANSACTION)
wait(ms.sms_was_received, msg)

wrong_msisdn = ms.msisdn + esme.msisdn
print('sending third sms (with wrong msisdn %s)' % wrong_msisdn)
msg = Sms(esme.msisdn, wrong_msisdn, 'smpp message with wrong dest')
esme.run_method_expect_failure(SMPP_ESME_RINVDSTADR, esme.sms_send_wait_resp, msg, esme.MSGMODE_TRANSACTION)

esme.disconnect()
