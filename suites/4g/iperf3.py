#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

def print_results(cli_res, srv_res):
    cli_sent = cli_res['end']['sum_sent']
    cli_recv = cli_res['end']['sum_received']
    print("RESULT client:")
    print("\tSEND: %d KB, %d kbps, %d seconds (%d retrans)" % (cli_sent['bytes']/1000, cli_sent['bits_per_second']/1000,  cli_sent['seconds'], cli_sent['retransmits']))
    print("\tRECV: %d KB, %d kbps, %d seconds" % (cli_recv['bytes']/1000, cli_recv['bits_per_second']/1000, cli_recv['seconds']))
    print("RESULT server:")
    print("\tSEND: %d KB, %d kbps, %d seconds" % (cli_sent['bytes']/1000, cli_sent['bits_per_second']/1000, cli_sent['seconds']))
    print("\tRECV: %d KB, %d kbps, %d seconds" % (cli_recv['bytes']/1000, cli_recv['bits_per_second']/1000, cli_recv['seconds']))


epc = suite.epc()
enb = suite.enb()
ue = suite.modem()
iperf3srv = suite.iperf3srv({'addr': epc.tun_addr()})
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
proc = iperf3cli.prepare_test_proc(ue.netns())

print('waiting for UE to attach...')
wait(ue.is_connected, None)
print('UE is attached')

print("Running iperf3 client to %s through %s" % (str(iperf3cli), ue.netns()))
proc.launch_sync()
iperf3srv.stop()
print_results(iperf3cli.get_results(), iperf3srv.get_results())
