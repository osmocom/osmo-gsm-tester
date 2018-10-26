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

hlr = suite.hlr()
bts = suite.bts()
pcu = bts.pcu()
mgw_msc = suite.mgw()
mgw_bsc = suite.mgw()
stp = suite.stp()
ggsn = suite.ggsn()
sgsn = suite.sgsn(hlr, ggsn)
msc = suite.msc(hlr, mgw_msc, stp)
bsc = suite.bsc(msc, mgw_bsc, stp)
ms = suite.modem()
iperf3srv = suite.iperf3srv()
iperf3cli = iperf3srv.create_client()

bsc.bts_add(bts)
sgsn.bts_add(bts)

print('start iperfv3 server...')
iperf3srv.start()

print('start network...')
hlr.start()
stp.start()
ggsn.start()
sgsn.start()
msc.start()
mgw_msc.start()
mgw_bsc.start()
bsc.start()

bts.start()
wait(bsc.bts_is_connected, bts)
print('Waiting for bts to be ready...')
wait(bts.ready_for_pcu)
pcu.start()

hlr.subscriber_add(ms)

ms.connect(msc.mcc_mnc())
ms.attach()

ms.log_info()

print('waiting for modems to attach...')
wait(ms.is_connected, msc.mcc_mnc())
wait(msc.subscriber_attached, ms)

print('waiting for modems to attach to data services...')
wait(ms.is_attached)

# We need to use inet46 since ofono qmi only uses ipv4v6 eua (OS#2713)
ctx_id_v4 = ms.activate_context(apn='inet46', protocol=ms.CTX_PROT_IPv4)
print("Setting up data plan for %r" % repr(ctx_id_v4))
ms.setup_context_data_plane(ctx_id_v4)

print("Running iperf3 client to %s through %r" % (iperf3srv.addr(),repr(ctx_id_v4)))
res = iperf3cli.run_test(ms.netns())
iperf3srv.stop()
print_results(res, iperf3srv.get_results())

ms.deactivate_context(ctx_id_v4)
