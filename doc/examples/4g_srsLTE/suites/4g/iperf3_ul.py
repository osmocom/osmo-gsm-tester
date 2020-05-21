#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

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

iperf3srv.start()
proc = iperf3cli.prepare_test_proc(False, ue.netns())

print('waiting for UE to attach...')
wait(ue.is_connected, None)
print('UE is attached')

print("Running iperf3 client to %s through %s" % (str(iperf3cli), ue.netns()))
proc.launch_sync()
iperf3srv.stop()

iperf3cli.print_results()
iperf3srv.print_results(iperf3cli.proto() == iperf3cli.PROTO_UDP)

max_rate = enb.ue_max_rate(downlink=False)
res_str = ue.verify_metric(max_rate * 0.8, operation='avg', metric='ul_brate', criterion='gt')
print(res_str)
test.set_report_stdout(res_str)
