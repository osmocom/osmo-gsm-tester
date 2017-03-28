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
    'type': 'val_type',
    'band': 'val_band',
    'location_area_code': 'val_bts.location_area_code',
    'base_station_id_code': 'val_bts.base_station_id_code',
    'unit_id': 'val_bts.unit_id',
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

vals = dict(
        vty_bind_ip='val_vty_bind_ip',
        abis_bind_ip='val_abis_bind_ip',
        mcc='val_mcc',
        mnc='val_mnc',
        net_name_short='val_net_name_short',
        net_name_long='val_net_name_long',
        net_auth_policy='val_net_auth_policy',
        encryption='val_encryption',
        smpp_bind_ip='val_smpp_bind_ip',
        ctrl_bind_ip='val_ctrl_bind_ip',
        bts_list=(mock_bts0, mock_bts1)
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
