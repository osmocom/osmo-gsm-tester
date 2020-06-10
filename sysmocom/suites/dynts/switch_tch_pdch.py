#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *


def activate_pdp(ms_mo, ms_mt):
    # We need to use inet46 since ofono qmi only uses ipv4v6 eua (OS#2713)
    ctx_id_v4_mo = ms_mo.activate_context(apn='inet46', protocol=ms_mo.CTX_PROT_IPv4)
    print('ms_mo pdp ctx %r activated' % repr(ctx_id_v4_mo))
    ctx_id_v4_mt = ms_mt.activate_context(apn='inet46', protocol=ms_mt.CTX_PROT_IPv4)
    print('ms_mt pdp ctx %r activated' % repr(ctx_id_v4_mt))
    sleep(5)
    ms_mo.deactivate_context(ctx_id_v4_mo)
    ms_mt.deactivate_context(ctx_id_v4_mt)

def make_call(ms_mo, ms_mt):
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
    ms_mo.call_hangup(mo_cid)
    ms_mt.call_hangup(mt_cid)
    wait(lambda: len(ms_mo.call_id_list()) == 0 and len(ms_mt.call_id_list()) == 0)
    print('hangup success')

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
ms_mo = tenv.modem()
ms_mt = tenv.modem()

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

hlr.subscriber_add(ms_mo)
hlr.subscriber_add(ms_mt)

ms_mo.connect(msc.mcc_mnc())
ms_mt.connect(msc.mcc_mnc())
ms_mo.attach()
ms_mt.attach()

ms_mo.log_info()
ms_mt.log_info()

print('waiting for modems to attach...')
wait(ms_mo.is_registered, msc.mcc_mnc())
wait(ms_mt.is_registered, msc.mcc_mnc())
wait(msc.subscriber_attached, ms_mo)
wait(msc.subscriber_attached, ms_mt)

print('waiting for modems to attach to data services...')
wait(ms_mo.is_attached)
wait(ms_mt.is_attached)

print('1: activate_pdp')
activate_pdp(ms_mo, ms_mt)
print('2: make_call')
make_call(ms_mo, ms_mt)
print('3: Wait 30 seconds to let PCU handle the PDCH channels again')
sleep(30)
print('3: activate_pdp')
activate_pdp(ms_mo, ms_mt)
print('4: make_call')
make_call(ms_mo, ms_mt)
print('Done!')
