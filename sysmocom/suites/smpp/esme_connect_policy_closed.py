#!/usr/bin/env python3

# This test checks following use-cases while in 'closed' policy:
# * SMPP interface of SMSC accepts SMPP clients (ESMEs) with password previously
#   defined in its configuration file.
# * SMPP interface of SMSC rejects ESMEs with known system id but wrong password.
# * SMPP interface of SMSC rejects ESEMs with unknown system id

from osmo_gsm_tester.testenv import *

SMPP_ESME_RINVPASWD = 0x0000000E
SMPP_ESME_RINVSYSID = 0x0000000F

hlr = tenv.hlr()
bts = tenv.bts()
mgw_msc = tenv.mgw()
stp = tenv.stp()
msc = tenv.msc(hlr, mgw_msc, stp)
smsc = msc.smsc

esme = tenv.esme()
esme_no_pwd = tenv.esme()
esme_no_pwd.set_password('')

smsc.set_smsc_policy(smsc.SMSC_POLICY_CLOSED)
smsc.esme_add(esme)
smsc.esme_add(esme_no_pwd)

stp.start()
hlr.start()
msc.start()
mgw_msc.start()

log('Test with correct credentials (no password)')
esme_no_pwd.connect()
esme_no_pwd.disconnect()

log('Test with correct credentials (no password, non empty)')
esme_no_pwd.set_password('foobar')
esme_no_pwd.connect()
esme_no_pwd.disconnect()

log('Test with correct credentials')
esme.connect()
esme.disconnect()

log('Test with bad password, checking for failure')
correct_password = esme.password
new_password = 'barfoo' if correct_password == 'foobar' else 'foobar'
esme.set_password(new_password)
esme.run_method_expect_failure(SMPP_ESME_RINVPASWD, esme.connect)
esme.set_password(correct_password)

log('Test with bad system_id, checking for failure')
correct_system_id = esme.system_id
new_system_id = 'barfoo' if correct_system_id == 'foobar' else 'foobar'
esme.set_system_id(new_system_id)
esme.run_method_expect_failure(SMPP_ESME_RINVSYSID, esme.connect)
esme.set_system_id(correct_system_id)
