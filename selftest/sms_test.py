#!/usr/bin/env python3

import _prep
from osmo_gsm_tester.obj import sms

print(sms.Sms())
print(sms.Sms())
print(sms.Sms())
msg = sms.Sms('123', '456')
print(str(msg))

msg2 = sms.Sms('123', '456')
print(str(msg2))
assert msg != msg2

msg2.msg = str(msg.msg)
print(str(msg2))
assert msg == msg2

assert msg == str(msg.msg)

# vim: expandtab tabstop=4 shiftwidth=4
