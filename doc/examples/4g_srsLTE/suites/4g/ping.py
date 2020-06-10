#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

epc = tenv.epc()
enb = tenv.enb()
ue = tenv.modem()

epc.subscriber_add(ue)
epc.start()
enb.ue_add(ue)
enb.start(epc)

print('waiting for ENB to connect to EPC...')
wait(epc.enb_is_connected, enb)
print('ENB is connected to EPC')

ue.connect(enb)
print('waiting for UE to attach...')
wait(ue.is_registered, None)
print('UE is attached')

proc = ue.run_netns_wait('ping', ('ping', '-c', '10', epc.tun_addr()))
output = proc.get_stdout()
print(output)
test.set_report_stdout(output)
