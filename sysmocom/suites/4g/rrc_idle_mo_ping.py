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
wait(ue.is_registered)
print('UE is RRC connected')

print('waiting until RRC connection gets released...')
wait(lambda: not ue.is_rrc_connected())
print('UE is RRC idle')

# Wait a bit
sleep(5)

# Generate MO traffic
proc = ue.run_netns_wait('ping', ('ping', '-c', '1', epc.tun_addr()))
output = proc.get_stdout()

# Check PRACH transmissions
num_prach_sent = ue.get_counter('prach_sent')
if num_prach_sent != 2:
    raise Exception("Expected to have sent exactly 2 PRACHs, but in fact sent {}".format(num_prach_sent))

print(output)
test.set_report_stdout(output)
