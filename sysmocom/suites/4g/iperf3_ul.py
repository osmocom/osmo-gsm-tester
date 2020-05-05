#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

def print_result_node(result, node_str):
    sent = result['end']['sum_sent']
    recv = result['end']['sum_received']
    print("Result %s:" % node_str)
    print("\tSEND: %d KB, %d kbps, %d seconds (%s retrans)" % (sent['bytes']/1000, sent['bits_per_second']/1000, sent['seconds'], str(sent.get('retransmits', 'unknown'))))
    print("\tRECV: %d KB, %d kbps, %d seconds" % (recv['bytes']/1000, recv['bits_per_second']/1000, recv['seconds']))

def print_results(cli_res, srv_res):
    print_result_node(cli_res, 'client')
    print_result_node(srv_res, 'server')

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
print_results(iperf3cli.get_results(), iperf3srv.get_results())

max_rate = enb.ue_max_rate(downlink=False)
res_str = ue.verify_metric(max_rate * 0.8, operation='avg', metric='ul_brate', criterion='gt')
print(res_str)
test.set_report_stdout(res_str)
