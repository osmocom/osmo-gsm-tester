#!/usr/bin/env python3

# This test checks following use-cases while in 'accept-all' policy:
# * SMPP interface of SMSC accepts SMPP clients (ESMEs) which do not appear on
#   the config file

from osmo_gsm_tester.testenv import *

nitb = suite.nitb()
smsc = nitb.smsc
esme = suite.esme()

# Here we deliberately omit calling smsc.esme_add() to avoid having it included
# in the smsc config.
smsc.set_smsc_policy(smsc.SMSC_POLICY_ACCEPT_ALL)
esme.set_smsc(smsc)

nitb.start()

# Due to accept-all policy, connect() should work even if we didn't previously
# configure the esme in the smsc, no matter the system_id / password we use.
log('Test connect with non-empty values in system_id and password')
esme.set_system_id('foo')
esme.set_password('bar')
esme.connect()
esme.disconnect()

log('Test connect with empty values in system_id and password')
esme.set_system_id('')
esme.set_password('')
esme.connect()
esme.disconnect()
