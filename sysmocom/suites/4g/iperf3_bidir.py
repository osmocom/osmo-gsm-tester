#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *
import os

# Overlay suite-specific templates folder if it exists
if os.path.isdir(os.path.join(os.path.dirname(__file__), 'templates')):
  tenv.set_overlay_template_dir(os.path.join(os.path.dirname(__file__), 'templates'))

# Retrieve the number of physical ue from the test suite configuration.
test_config = tenv.config_test_specific()
nof_ue = int(test_config.get("nof_physical_ue", 1))

print(f'Number of physical ue: {nof_ue}')

ue_li = []

# Get the ue from the test configuration.
for n in range(0, nof_ue):
  ue_li.append(tenv.modem())
  print(f'ue index{n}: {ue_li[n]}')

epc = tenv.epc()
enb = tenv.enb()

iperf3srv = []
for n in range(0, nof_ue):
  iperf3srv.append(tenv.iperf3srv({'addr': epc.tun_addr()}))
  iperf3srv[n].set_run_node(epc.run_node())
  iperf3srv[n].set_port(iperf3srv[n].DEFAULT_SRV_PORT + n)

# Set the iperf clients in the ue.
iperf3cli = []
for n in range(0, nof_ue):
  iperf3cli.append(iperf3srv[n].create_client())
  iperf3cli[n].set_run_node(ue_li[n].run_node())

for n in range(0, nof_ue):
  epc.subscriber_add(ue_li[n])
epc.start()

enb.ue_add(ue_li[0])
enb.start(epc)

print('waiting for ENB to connect to EPC...')
wait(epc.enb_is_connected, enb)
print('ENB is connected to EPC')

for n in range(0, nof_ue):
  ue_li[n].connect(enb)

for n in range(0, nof_ue):
  iperf3srv[n].start()

proc_li = []

# Attach all the ue's.
for n in range(0, nof_ue):
  max_rate_dl = enb.ue_max_rate(downlink=True, num_carriers=ue_li[n].num_carriers)
  client = iperf3cli[n].prepare_test_proc(iperf3cli[n].DIR_BI, ue_li[n].netns(), bitrate=max_rate_dl)
  print(f'Iperf client type: {type(client)}')
  proc_li.append(client)

# Wait for all the ue's attach.
for n in range(0, nof_ue):
  print(f'waiting for UE {n} to attach...')
  wait(ue_li[n].is_registered)
  print(f'UE {n} is attached')

# Execute the iperfs and wait for its finish.
try:
  for proc in proc_li:
    proc.launch()
  for proc in proc_li:
    proc.wait()
except Exception as e:
  for proc in proc_li:
    try:
      proc.terminate()
    except Exception:
      print("Exception while terminanting process %r" % repr(process))
  raise e

for n in range(0, nof_ue):
  iperf3cli[n].print_results()
  iperf3srv[n].print_results(iperf3cli[n].proto() == iperf3cli[n].PROTO_UDP)

# 80% of the maximum rate for half of the test duration
max_rate_ratio = 0.8
out = ''
for n in range(0, nof_ue):
  half_duration = int(round(iperf3cli[n].time_sec() / 2))
  max_rate_dl = enb.ue_max_rate(downlink=True, num_carriers=ue_li[n].num_carriers)
  max_rate_ul = enb.ue_max_rate(downlink=False, num_carriers=ue_li[n].num_carriers)
  res_str = ue_li[n].verify_metric((max_rate_dl + max_rate_ul) * max_rate_ratio, operation='max_rolling_avg', metric='dl_brate+ul_brate', criterion='gt', window=half_duration)
  print(res_str)
  out += res_str
  if n != nof_ue - 1:
    out += '\n'

test.set_report_stdout(out)