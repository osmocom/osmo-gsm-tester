#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *
from osmo_gsm_tester.obj.osmo_ctrl import *

hlr = tenv.hlr()
bts0 = tenv.bts()
bts1 = tenv.bts()
mgw_msc = tenv.mgw()
mgw_bsc = tenv.mgw()
stp = tenv.stp()
msc = tenv.msc(hlr, mgw_msc, stp)
bsc = tenv.bsc(msc, mgw_bsc, stp)
ms0 = tenv.modem()
ms1 = tenv.modem()

hlr.start()
stp.start()
msc.start()
mgw_msc.start()
mgw_bsc.start()
bsc.bts_add(bts0)
bsc.bts_add(bts1)
bsc.start()

# prevent handovers from measurement reports, enable handover so that
# triggering handover from VTY works.
bsc.vty.cmds(
        'enable',
         'configure terminal',
          'network',
           'handover algorithm 2',
           'handover2 min rxlev -110',
           'handover2 min rxqual 7',
           'handover2 power budget hysteresis 999',
           'handover 1',
         'end')
# now back on the 'enable' node.

# first start only the first BTS, to make sure both modems subscribe there
with test.report_fragment('01_bts0_started'):
    bts0.start()
    wait(bsc.bts_is_connected, bts0)

hlr.subscriber_add(ms0)
hlr.subscriber_add(ms1)

ms0.connect(msc.mcc_mnc())
ms1.connect(msc.mcc_mnc())

ms0.log_info()
ms1.log_info()

print('waiting for modems to attach...')

with test.report_fragment('02.1_ms0_attach'):
    wait(ms0.is_registered, msc.mcc_mnc())

with test.report_fragment('02.2_ms1_attach'):
    wait(ms1.is_registered, msc.mcc_mnc())

with test.report_fragment('02.3_subscribed_in_msc'):
    wait(msc.subscriber_attached, ms0, ms1)

assert len(ms0.call_id_list()) == 0 and len(ms1.call_id_list()) == 0
mo_cid = ms0.call_dial(ms1)
mt_cid = ms1.call_wait_incoming(ms0)
print('dial success')

with test.report_fragment('03_call_established'):
    assert not ms0.call_is_active(mo_cid) and not ms1.call_is_active(mt_cid)
    ms1.call_answer(mt_cid)
    wait(ms0.call_is_active, mo_cid)
    wait(ms1.call_is_active, mt_cid)
    print('answer success, call established and ongoing')

    assert bsc.vty.active_lchans_match(
            expected=('0-0-2-0 TCH/F ESTABLISHED',
                      '0-0-3-0 TCH/F ESTABLISHED'))

# call is connected; start up the second BTS so that we can trigger a handover to it
with test.report_fragment('04.1_bts1_started'):
    bts1.start()
    wait(bsc.bts_is_connected, bts1)

print('wait a bit for modems to see bts1')
sleep(10.0)
# TODO evaluate measurement reports instead?

counter_names = (
        'handover:completed',
        'handover:stopped',
        'handover:no_channel',
        'handover:timeout',
        'handover:failed',
        'handover:error',
        )
counters = RateCounters('bsc', counter_names, from_ctrl=bsc.ctrl)
counters.add(RateCounters('bts', counter_names, instances=(0, 1)))

def do_handover(initial_lchans, target_lchan, vty_cmd, final_lchans, attempts=5):
    worked = False
    while (attempts > 0) and (not worked):
        # make sure the call is still active as expected
        assert bsc.vty.active_lchans_match(**initial_lchans)
        # make sure the handover target lchan is unused (maybe waiting after previous error)
        wait(bsc.vty.active_lchans_match, **target_lchan, timeout=20)

        counters.read()
        log_mark = bsc.process.get_output_mark('stderr')

        print('trigger handover: %s' % vty_cmd)
        bsc.vty.cmd(vty_cmd)

        print('wait for handover counters to change...')
        wait(counters.changed, timeout=20)
        print(counters.diff.str(skip_zero_vals=True))

        print('\n'+'\n'.join(bsc.process.grep_output('stderr', r'\bhandover\(|\bDCHAN\b', log_mark)))

        worked = bsc.vty.active_lchans_match(**final_lchans)
        if not worked and attempts > 0:
            attempts -= 1
            print('did not work, try again... (attempts left: %d)' % attempts)
    return worked


with test.report_fragment('05.1_handover_ms0'):
    assert do_handover(
        initial_lchans=dict(
                expected=('0-0-2-0 TCH/F ESTABLISHED',
                          '0-0-3-0 TCH/F ESTABLISHED'),
            ),
        target_lchan=dict(
                not_expected=('1-0-2-0',),
            ),
        vty_cmd='bts 0 trx 0 timeslot 2 sub-slot 0 handover 1',
        final_lchans=dict(
                expected=('0-0-3-0 TCH/F ESTABLISHED',
                          '1-0-2-0 TCH/F ESTABLISHED',),
                not_expected=('0-0-2-0 TCH/F ESTABLISHED',),
            ),
        )

with test.report_fragment('05.2_handover_ms1'):
    assert do_handover(
        initial_lchans=dict(
                expected=('0-0-3-0 TCH/F ESTABLISHED',
                          '1-0-2-0 TCH/F ESTABLISHED'),
            ),
        target_lchan=dict(
                not_expected=('1-0-3-0',),
            ),
        vty_cmd='bts 0 trx 0 timeslot 3 sub-slot 0 handover 1',
        final_lchans=dict(
                expected=('1-0-2-0 TCH/F ESTABLISHED',
                          '1-0-3-0 TCH/F ESTABLISHED',),
                not_expected=('0-0-2-0 TCH/F ESTABLISHED',
                              '0-0-3-0 TCH/F ESTABLISHED',),
            ),
        )

with test.report_fragment('06_call_stable'):
    print('expect the call to continue for a while, to ensure the new lchan is functional')
    for i in range(5):
        sleep(5)
        assert bsc.vty.active_lchans_match(
                expected=('1-0-2-0 TCH/F ESTABLISHED',
                          '1-0-3-0 TCH/F ESTABLISHED',))
        print('call is still fine')

print('handover back (test the other BTS model)')

with test.report_fragment('07.1_handover_ms1_back'):
    assert do_handover(
        initial_lchans=dict(
                expected=('1-0-2-0 TCH/F ESTABLISHED',
                          '1-0-3-0 TCH/F ESTABLISHED'),
            ),
        target_lchan=dict(
                not_expected=('0-0-2-0',),
            ),
        vty_cmd='bts 1 trx 0 timeslot 3 sub-slot 0 handover 0',
        final_lchans=dict(
                expected=('0-0-2-0 TCH/F ESTABLISHED',
                          '1-0-2-0 TCH/F ESTABLISHED',),
                not_expected=('1-0-3-0 TCH/F ESTABLISHED',),
            ),
        )

with test.report_fragment('07.2_handover_ms0_back'):
    assert do_handover(
        initial_lchans=dict(
                expected=('0-0-2-0 TCH/F ESTABLISHED',
                          '1-0-2-0 TCH/F ESTABLISHED'),
            ),
        target_lchan=dict(
                not_expected=('0-0-3-0',),
            ),
        vty_cmd='bts 1 trx 0 timeslot 2 sub-slot 0 handover 0',
        final_lchans=dict(
                expected=('0-0-2-0 TCH/F ESTABLISHED',
                          '0-0-3-0 TCH/F ESTABLISHED',),
                not_expected=('1-0-2-0 TCH/F ESTABLISHED',
                              '1-0-3-0 TCH/F ESTABLISHED',),
            ),
        )

with test.report_fragment('08_call_stable'):
    print('expect the call to continue for a while, to ensure the new lchan is functional')
    for i in range(5):
        sleep(5)
        assert bsc.vty.active_lchans_match(
                expected=('0-0-2-0 TCH/F ESTABLISHED',
                          '0-0-3-0 TCH/F ESTABLISHED',))
        print('call is still fine')

assert ms0.call_is_active(mo_cid) and ms1.call_is_active(mt_cid)
ms1.call_hangup(mt_cid)
wait(lambda: len(ms0.call_id_list()) == 0 and len(ms1.call_id_list()) == 0)
print('hangup success')

# vim: tabstop=4 shiftwidth=4 expandtab
