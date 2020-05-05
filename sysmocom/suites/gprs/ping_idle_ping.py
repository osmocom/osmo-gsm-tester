#!/usr/bin/env python3

# Following test verifies GPRS works fine after MS stays idle (no data
# sent/received) for a long while.
# See OS#3678 and OS#2455 for more information.

from osmo_gsm_tester.testenv import *

hlr = tenv.hlr()
bts = tenv.bts()
pcu = bts.pcu()
mgw_msc = tenv.mgw()
mgw_bsc = tenv.mgw()
stp = tenv.stp()
ggsn = tenv.ggsn()
sgsn = tenv.sgsn(hlr, ggsn)
msc = tenv.msc(hlr, mgw_msc, stp)
bsc = tenv.bsc(msc, mgw_bsc, stp)
ms = tenv.modem()

bsc.bts_add(bts)
sgsn.bts_add(bts)

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
print("Setting up data plane for %r" % repr(ctx_id_v4))
ms.setup_context_data_plane(ctx_id_v4)
str = "[1] Running 10 ping requests for %r" % repr(ctx_id_v4)
output = str + '\n'
print(str)
proc = ms.run_netns_wait('ping1', ('ping', '-c', '10', ggsn.addr()))
str = proc.get_stdout()
output += str
print(str)

str = "Sleeping for 60 seconds"
output += str + '\n'
print(str)
sleep(60)

str = "[2] Running 10 ping requests for %r" % repr(ctx_id_v4)
output += str + '\n'
print(str)
proc = ms.run_netns_wait('ping2', ('ping', '-c', '10', ggsn.addr()))
str = proc.get_stdout()
output += str
print(str)

ms.deactivate_context(ctx_id_v4)

test.set_report_stdout(output)
