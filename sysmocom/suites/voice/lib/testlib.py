#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

def test_mo_mt_call(use_osmux=False, force_osmux=False):
    hlr = tenv.hlr()
    bts = tenv.bts()
    mgw_msc = tenv.mgw()
    mgw_bsc = tenv.mgw()
    stp = tenv.stp()
    msc = tenv.msc(hlr, mgw_msc, stp)
    bsc = tenv.bsc(msc, mgw_bsc, stp)
    ms_mo = tenv.modem()
    ms_mt = tenv.modem()

    hlr.start()
    stp.start()

    msc.set_use_osmux(use_osmux, force_osmux)
    msc.start()

    # osmo-msc still doesn't support linking 2 internal leg calls through Osmux
    # if both calls are using Osmux. Currently, RTP is always used between the 2
    # endpoints of the MGW. See OS#4065.
    mgw_msc.set_use_osmux(use_osmux, False)
    mgw_msc.start()

    # We don't want to force Osmux in BSC_MGW since in MGW BTS-side is still RTP.
    mgw_bsc.set_use_osmux(use_osmux, False)
    mgw_bsc.start()

    bsc.set_use_osmux(use_osmux, force_osmux)
    bsc.bts_add(bts)
    bsc.start()

    bts.start()
    wait(bsc.bts_is_connected, bts)

    hlr.subscriber_add(ms_mo)
    hlr.subscriber_add(ms_mt)

    ms_mo.connect(msc.mcc_mnc())
    ms_mt.connect(msc.mcc_mnc())

    ms_mo.log_info()
    ms_mt.log_info()

    print('waiting for modems to attach...')
    wait(ms_mo.is_connected, msc.mcc_mnc())
    wait(ms_mt.is_connected, msc.mcc_mnc())
    wait(msc.subscriber_attached, ms_mo, ms_mt)

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
