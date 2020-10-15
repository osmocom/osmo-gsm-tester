#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

hlr = tenv.hlr()
bts = tenv.bts()
mgw_msc = tenv.mgw()
mgw_bsc = tenv.mgw()
stp = tenv.stp()
msc = tenv.msc(hlr, mgw_msc, stp)
bsc = tenv.bsc(msc, mgw_bsc, stp)
ms_mo = tenv.modem()
ms_mt = tenv.modem()
ms_mo_emerg = tenv.modem()
ms_mt_emerg = tenv.modem()

# Configure timeslots so that only 1 concurrent call (MO MT, 2 MS) is allowed
bts.set_num_trx(1)
bts.set_trx_phy_channel(0, 0, 'CCCH+SDCCH4')
bts.set_trx_phy_channel(0, 1, 'TCH/F')
bts.set_trx_phy_channel(0, 2, 'TCH/F')
bts.set_trx_phy_channel(0, 3, 'PDCH')
bts.set_trx_phy_channel(0, 4, 'PDCH')
bts.set_trx_phy_channel(0, 5, 'PDCH')
bts.set_trx_phy_channel(0, 6, 'PDCH')
bts.set_trx_phy_channel(0, 7, 'PDCH')

hlr.start()
stp.start()

# Set MSC to route emergency call to ms_mt_emerg:
msc.set_emergency_call_msisdn(ms_mt_emerg.msisdn())
msc.start()

mgw_msc.start()
mgw_bsc.start()

bsc.bts_add(bts)
bsc.start()

bts.start()
wait(bsc.bts_is_connected, bts)

hlr.subscriber_add(ms_mo)
hlr.subscriber_add(ms_mt)
hlr.subscriber_add(ms_mo_emerg)
hlr.subscriber_add(ms_mt_emerg)

ms_mo.connect(msc.mcc_mnc())
ms_mt.connect(msc.mcc_mnc())
ms_mo_emerg.connect(msc.mcc_mnc())
ms_mt_emerg.connect(msc.mcc_mnc())

ms_mo.log_info()
ms_mt.log_info()
ms_mo_emerg.log_info()
ms_mt_emerg.log_info()

print('waiting for modems to attach...')
wait(ms_mo.is_registered, msc.mcc_mnc())
wait(ms_mt.is_registered, msc.mcc_mnc())
wait(ms_mo_emerg.is_registered, msc.mcc_mnc())
wait(ms_mt_emerg.is_registered, msc.mcc_mnc())
wait(msc.subscriber_attached, ms_mo, ms_mt, ms_mo_emerg, ms_mt_emerg)

# Initiating first call between ms_mo and ms_mt. It should be dropped when later an emergency call comes in
assert len(ms_mo.call_id_list()) == 0 and len(ms_mt.call_id_list()) == 0
mo_cid = ms_mo.call_dial(ms_mt)
mt_cid = ms_mt.call_wait_incoming(ms_mo)
print('dial success')
assert not ms_mo.call_is_active(mo_cid) and not ms_mt.call_is_active(mt_cid)
ms_mt.call_answer(mt_cid)
assert len(ms_mo.call_id_list()) == 1 and len(ms_mt.call_id_list()) == 1

sleep(5) # maintain the normal call active for 5 seconds

assert len(ms_mo.call_id_list()) == 1 and len(ms_mt.call_id_list()) == 1
assert len(ms_mo_emerg.call_id_list()) == 0 and len(ms_mt_emerg.call_id_list()) == 0
# Calling emergency number should be redirected to ms_mt as configured further above:
emerg_numbers = ms_mo_emerg.emergency_numbers()
assert len(emerg_numbers) > 0
print('dialing Emergency Number %s' % (emerg_numbers[0]))
mo_cid_emerg = ms_mo_emerg.call_dial(emerg_numbers[0])
mt_cid_emerg = ms_mt_emerg.call_wait_incoming(ms_mo_emerg)
print('dial success')
assert not ms_mo_emerg.call_is_active(mo_cid_emerg) and not ms_mt_emerg.call_is_active(mt_cid_emerg)
ms_mt_emerg.call_answer(mt_cid_emerg)
wait(ms_mo_emerg.call_is_active, mo_cid_emerg)
wait(ms_mt_emerg.call_is_active, mt_cid_emerg)
print('answer success, call established and ongoing')

# Now the emergency call is ongoing, and the previous one should have been gone:
assert len(ms_mo.call_id_list()) == 0 and len(ms_mt.call_id_list()) == 0

sleep(5) # maintain the emergency call active for 5 seconds

assert ms_mo_emerg.call_is_active(mo_cid_emerg) and ms_mt.call_is_active(mt_cid_emerg)
ms_mt_emerg.call_hangup(mt_cid_emerg)
wait(lambda: len(ms_mo_emerg.call_id_list()) == 0 and len(ms_mt_emerg.call_id_list()) == 0)
print('hangup success')
