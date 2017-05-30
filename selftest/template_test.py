#!/usr/bin/env python3

import _prep

import sys
import os

from osmo_gsm_tester import template, log

log.set_level(log.C_CNF, log.L_DBG)

print('- Testing: fill a config file with values')

mock_timeslot_list=(
        { 'phys_chan_config': 'val_phys_chan_config_0' },
        { 'phys_chan_config': 'val_phys_chan_config_1' },
        { 'phys_chan_config': 'val_phys_chan_config_2' },
        { 'phys_chan_config': 'val_phys_chan_config_3' },
        )

mock_bts = {
    'osmobsc_bts_type': 'val_type',
    'band': 'val_band',
    'location_area_code': 'val_bts.location_area_code',
    'base_station_id_code': 'val_bts.base_station_id_code',
    'ipa_unit_id': 'val_bts.unit_id',
    'stream_id': 'val_bts.stream_id',
    'trx_list': (
            dict(arfcn='val_trx_arfcn_trx0',
                max_power_red='val_trx_max_power_red_trx0',
                timeslot_list=mock_timeslot_list),
            dict(arfcn='val_trx_arfcn_trx1',
                max_power_red='val_trx_max_power_red_trx1',
                timeslot_list=mock_timeslot_list),
            )
}

mock_esme = {
    'system_id': 'val_system_id',
    'password': 'val_password'
}

def clone_mod(d, val_ext):
    c = dict(d)
    for name in c.keys():
        if isinstance(c[name], str):
            c[name] = c[name] + val_ext
        elif isinstance(c[name], dict):
            c[name] = clone_mod(c[name], val_ext)
    return c

mock_bts0 = clone_mod(mock_bts, '_bts0')
mock_bts1 = clone_mod(mock_bts, '_bts1')

mock_esme0 = clone_mod(mock_esme, '_esme0')
mock_esme1 = clone_mod(mock_esme, '_esme1')
mock_esme1['password'] = ''

vals = dict(nitb=dict(
                    net=dict(
                        mcc='val_mcc',
                        mnc='val_mnc',
                        short_name='val_short_name',
                        long_name='val_long_name',
                        auth_policy='val_auth_policy',
                        encryption='val_encryption',
                        bts_list=(mock_bts0, mock_bts1)
                    ),
                    ip_address=dict(addr='val_ip_address'),
            ),
            smsc=dict(
                policy='val_smsc_policy',
                esme_list=(mock_esme0, mock_esme1)
            ),
       )

print(template.render('osmo-nitb.cfg', vals))

print('- Testing: expect to fail on invalid templates dir')
try:
    template.set_templates_dir('non-existing dir')
    sys.stderr.write('Error: setting non-existing templates dir should raise RuntimeError\n')
    assert(False)
except RuntimeError:
    # not logging exception to omit non-constant path name from expected output
    print('sucess: setting non-existing templates dir raised RuntimeError\n')
    pass

# vim: expandtab tabstop=4 shiftwidth=4
