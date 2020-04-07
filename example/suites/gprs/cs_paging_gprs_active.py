#!/usr/bin/env python3

# Following test verifies CS paging works when MS is GPRS  attached.
# See OS#2204 for more information.

from osmo_gsm_tester.testenv import *

import testlib
suite.test_import_modules_register_for_cleanup(testlib)
from testlib import setup_run_iperf3_test_parallel

def ready_cb_place_voicecall(ms_li):
    print('waiting a few secs to make sure iperf3 test is running')
    sleep(2)
    # At this point in time, TBF should be enabled on both MS since they are sending/receiving data.
    print('iperf3 running, let\'s place a call')
    ms_mo = ms_li[0]
    ms_mt = ms_li[1]
    assert len(ms_mo.call_id_list()) == 0 and len(ms_mt.call_id_list()) == 0
    mo_cid = ms_mo.call_dial(ms_mt)
    mt_cid = ms_mt.call_wait_incoming(ms_mo)
    print('dial success')

    assert not ms_mo.call_is_active(mo_cid) and not ms_mt.call_is_active(mt_cid)
    ms_mt.call_answer(mt_cid)
    wait(ms_mo.call_is_active, mo_cid)
    wait(ms_mt.call_is_active, mt_cid)
    print('answer success, call established and ongoing')

    sleep(5) # maintain the call active for 5 seconds

    assert ms_mo.call_is_active(mo_cid) and ms_mt.call_is_active(mt_cid)
    ms_mt.call_hangup(mt_cid)
    wait(lambda: len(ms_mo.call_id_list()) == 0 and len(ms_mt.call_id_list()) == 0)
    print('hangup success')


setup_run_iperf3_test_parallel(2, ready_cb=ready_cb_place_voicecall)
