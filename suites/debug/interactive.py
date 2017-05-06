#!/usr/bin/env python3
from osmo_gsm_tester.test import *

print('use resources...')
nitb = suite.nitb()
bts = suite.bts()
modems = suite.modems(int(prompt('How many modems?')))

print('start nitb and bts...')
nitb.bts_add(bts)
nitb.start()
bts.start()

for m in modems:
  nitb.subscriber_add(m)
  m.connect(nitb)

while True:
  cmd = prompt('Enter command: (q)uit (s)ms (g)et-registered (w)ait-registered')
  cmd = cmd.strip().lower()

  if not cmd:
    continue
  if 'quit'.startswith(cmd):
    break
  elif 'wait-registered'.startswith(cmd):
    wait(nitb.subscriber_attached, *modems)
  elif 'get-registered'.startswith(cmd):
    print(nitb.imsi_list_attached())
    print('RESULT: %s' %
       ('All modems are registered.' if nitb.subscriber_attached(*modems)
        else 'Some modem(s) not registered yet.'))
  elif 'sms'.startswith(cmd):
    for mo in modems:
      for mt in modems:
        mo.sms_send(mt.msisdn, 'to ' + mt.name())
