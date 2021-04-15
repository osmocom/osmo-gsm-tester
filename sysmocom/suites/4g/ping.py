#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *
import os

# Overlay suite-specific templates folder if it exists
if os.path.isdir(os.path.join(os.path.dirname(__file__), 'templates')):
  tenv.set_overlay_template_dir(os.path.join(os.path.dirname(__file__), 'templates'))

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
print('UE is attached')

proc = ue.run_netns_wait('ping', ('ping', '-c', '10', epc.tun_addr()))

# Check zero lost pings
num_sent = int([x for x in proc.get_stdout().split('\n') if x.find('packets transmitted') != -1][0].split(' ')[0])
num_received = int([x for x in proc.get_stdout().split('\n') if x.find('packets transmitted, ') != -1][0].split('packets transmitted, ')[1].split(' received')[0])
if num_received != num_sent:
  raise Exception("{}\n\nError: Detected {} lost pings".format(proc.get_stdout(), num_sent - num_received))

output = proc.get_stdout()
print(output)
test.set_report_stdout(output)