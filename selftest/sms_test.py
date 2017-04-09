#!/usr/bin/env python3

import _prep
from osmo_gsm_tester import ofono_client

print(ofono_client.Sms())
print(ofono_client.Sms())
print(ofono_client.Sms())
sms = ofono_client.Sms('123', '456')
print(str(sms))

sms2 = ofono_client.Sms('123', '456')
print(str(sms2))
assert sms != sms2

sms2.msg = str(sms.msg)
print(str(sms2))
assert sms == sms2

# vim: expandtab tabstop=4 shiftwidth=4
