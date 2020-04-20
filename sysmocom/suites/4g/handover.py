#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

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
proc = iperf3cli.prepare_test_proc(False, ue.netns(), 30)

print('waiting for UE to attach...')
wait(ue.is_connected, None)
print('UE is attached')

rfemu_cell1 = enb.get_rfemu(0)
rfemu_cell2 = enb.get_rfemu(1)

# attenuation from 0 to 10, then back to 0
cell1_att_li = list(range(0, 11, 1)) + list(range(9, -1, -1))
# attenuation from 10 to 0, then back to 10
cell2_att_li = list(range(10, 0, -1)) + list(range(0, 11, 1))

try:
    proc.launch()
    step = 0
    while step < len(cell1_att_li):
        rfemu_cell1.set_attenuation(cell1_att_li[step])
        rfemu_cell2.set_attenuation(cell2_att_li[step])
        step += 1
        sleep(1)
    num_handovers = ue.get_counter('handover_success')
    if num_handovers != 2:
        raise Exception('Wrong number of handovers %d vs expected 2' % num_handovers)
except Exception as e:
    try:
        proc.terminate() # make sure we always terminate the process
    except Exception:
            print("Exception while terminating process %r" % repr(process))
    raise e

rest_str = 'Got %d successful handovers' % num_handovers
print(res_str)
test.set_report_stdout(res_str)
proc.terminate()
proc.wait()
print("Done")
