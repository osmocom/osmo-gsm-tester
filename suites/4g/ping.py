#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

epc = suite.epc()
enb = suite.enb()
ue = suite.modem()

epc.subscriber_add(ue)
epc.start()
enb.ue_add(ue)
enb.start(epc)

print('waiting for ENB to connect to EPC...')
wait(epc.enb_is_connected, enb)
print('ENB is connected to EPC')

ue.connect(enb)
print('waiting for UE to attach...')
wait(ue.is_connected, None)
print('UE is attached')

ue.run_netns_wait('ping', ('ping', '-c', '10', epc.tun_addr()))
