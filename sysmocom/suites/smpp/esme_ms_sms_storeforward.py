#!/usr/bin/env python3

# This test checks following use-cases:
# * SMPP interface of SMSC accepts SMPP clients (ESMEs) with password previously
#   defined in its configuration file.
# * When SMS is sent in 'store & forward' mode, ESME fails to send an SMS to non registered MS.
# * When SMS is sent in 'store & forward' mode, ESME can send an SMS to a not yet registered MS.
# * When SMS is sent in 'store & forward' mode, ESME can send an SMS to an already registered MS.
# * When SMS is sent in 'store & forward' mode, ESME receives a SMS receipt if it asked for it.

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

wrong_msisdn = ms.msisdn() + esme.msisdn
print('sending sms with wrong msisdn %s, it will be stored but not delivered' % wrong_msisdn)
msg = Sms(esme.msisdn, wrong_msisdn, 'smpp message with wrong dest')
# Since osmo-msc 1e67fea7ba5c6336, we accept all sms in store&forward mode without looking at HLR
# esme.run_method_expect_failure(SMPP_ESME_RINVDSTADR, esme.sms_send_wait_resp, msg, esme.MSGMODE_STOREFORWARD)
umref_wrong = esme.sms_send_wait_resp(msg, esme.MSGMODE_STOREFORWARD, receipt=True)

print('sending sms, it will be stored...')
msg = Sms(esme.msisdn, ms.msisdn(), 'smpp send not-yet-registered message')
umref = esme.sms_send_wait_resp(msg, esme.MSGMODE_STOREFORWARD, receipt=True)

print('MS registers and will receive the SMS...')
ms.connect(msc.mcc_mnc())
wait(ms.is_registered, msc.mcc_mnc())
wait(msc.subscriber_attached, ms)
wait(ms.sms_was_received, msg)
print('Waiting to receive and consume sms receipt with reference', umref)
wait(esme.receipt_was_received, umref)

print('checking MS can receive SMS while registered...')
msg = Sms(esme.msisdn, ms.msisdn(), 'smpp send already-registered message')
umref = esme.sms_send_wait_resp(msg, esme.MSGMODE_STOREFORWARD, receipt=True)
wait(ms.sms_was_received, msg)
print('Waiting to receive and consume sms receipt with reference', umref)
wait(esme.receipt_was_received, umref)

print('Asserting the sms with wrong msisdn was not delivered', umref_wrong)
assert not esme.receipt_was_received(umref_wrong)

esme.disconnect()
