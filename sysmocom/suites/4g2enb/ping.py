#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

epc = tenv.epc()
enbA = tenv.enb()
enbB = tenv.enb()
ue = tenv.modem()

epc.subscriber_add(ue)
epc.start()
enbA.ue_add(ue)
enbB.ue_add(ue)
enbA.start(epc)
enbB.start(epc)

print('waiting for ENBs to connect to EPC...')
wait(epc.enb_is_connected, enbA)
wait(epc.enb_is_connected, enbB)
print('ENBs is connected to EPC')

ue.connect(enbA)
print('waiting for UE to attach...')
wait(ue.is_registered)
print('UE is attached')

proc = ue.run_netns_wait('ping', ('ping', '-c', '10', epc.tun_addr()))
output = proc.get_stdout()
print(output)
test.set_report_stdout(output)
