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

nitb = suite.nitb()
bts = suite.bts()
ms = suite.modem()
esme = suite.esme()

print('start nitb and bts...')
nitb.bts_add(bts)
nitb.smsc.esme_add(esme)
nitb.start()
bts.start()

esme.connect()
nitb.subscriber_add(ms)

wrong_msisdn = ms.msisdn + esme.msisdn
print('sending sms with wrong msisdn %s, it will fail' % wrong_msisdn)
msg = Sms(esme.msisdn, wrong_msisdn, 'smpp message with wrong dest')
esme.run_method_expect_failure(SMPP_ESME_RINVDSTADR, esme.sms_send_wait_resp, msg, esme.MSGMODE_STOREFORWARD)

print('sending sms, it will be stored...')
msg = Sms(esme.msisdn, ms.msisdn, 'smpp send not-yet-registered message')
umref = esme.sms_send_wait_resp(msg, esme.MSGMODE_STOREFORWARD, receipt=True)

print('MS registers and will receive the SMS...')
ms.connect(nitb.mcc_mnc())
wait(ms.is_connected, nitb.mcc_mnc())
wait(nitb.subscriber_attached, ms)
wait(ms.sms_was_received, msg)
print('Waiting to receive and consume sms receipt with reference', umref)
wait(esme.receipt_was_received, umref)

print('checking MS can receive SMS while registered...')
msg = Sms(esme.msisdn, ms.msisdn, 'smpp send already-registered message')
umref = esme.sms_send_wait_resp(msg, esme.MSGMODE_STOREFORWARD, receipt=True)
wait(ms.sms_was_received, msg)
print('Waiting to receive and consume sms receipt with reference', umref)
wait(esme.receipt_was_received, umref)
esme.disconnect()
