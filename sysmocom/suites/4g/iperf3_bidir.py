#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *
import os

# Overlay suite-specific templates folder if it exists
if os.path.isdir(os.path.join(os.path.dirname(__file__), 'templates')):
  tenv.set_overlay_template_dir(os.path.join(os.path.dirname(__file__), 'templates'))

epc = tenv.epc()
enb = tenv.enb()
ue = tenv.modem()
iperf3srv = tenv.iperf3srv({'addr': epc.tun_addr()})
iperf3srv.set_run_node(epc.run_node())
iperf3cli = iperf3srv.create_client()
iperf3cli.set_run_node(ue.run_node())

epc.subscriber_add(ue)
epc.start()
enb.ue_add(ue)
enb.start(epc)

print('waiting for ENB to connect to EPC...')
wait(epc.enb_is_connected, enb)
print('ENB is connected to EPC')

ue.connect(enb)

max_rate_ratio = 0.8
max_rate_dl = enb.ue_max_rate(downlink=True, num_carriers=ue.num_carriers)
max_rate_ul = enb.ue_max_rate(downlink=False, num_carriers=ue.num_carriers)

iperf3srv.start()
proc = iperf3cli.prepare_test_proc(iperf3cli.DIR_BI, ue.netns(), bitrate=max_rate_dl)

print('waiting for UE to attach...')
wait(ue.is_registered)
print('UE is attached')

print("Running iperf3 client to %s through %s" % (str(iperf3cli), ue.netns()))
proc.launch_sync()
iperf3srv.stop()

iperf3cli.print_results()
iperf3srv.print_results(iperf3cli.proto() == iperf3cli.PROTO_UDP)

# 80% of the maximum rate for half of the test duration
half_duration = int(round(iperf3cli.time_sec() / 2))
res_str = ue.verify_metric((max_rate_dl + max_rate_ul) * max_rate_ratio, operation='max_rolling_avg', metric='dl_brate+ul_brate', criterion='gt', window=half_duration)
print(res_str)
test.set_report_stdout(res_str)