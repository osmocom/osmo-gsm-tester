#!/usr/bin/env python3

import _prep

import sys
import os
import io
import pprint
import copy

from osmo_gsm_tester import config, log

example_config_file = 'test.cfg'
example_config = os.path.join(_prep.script_dir, 'config_test', example_config_file)
cfg = config.read(example_config)

pprint.pprint(cfg)

test_schema = {
    'modems[].dbus_path': config.STR,
    'modems[].msisdn': config.STR,
    'modems[].imsi': config.STR,
    'modems[].ki': config.STR,
    'bts[].name' : config.STR,
    'bts[].type' : config.STR,
    'bts[].addr' : config.STR,
    'bts[].trx[].timeslots[]' : config.STR,
    'bts[].trx[].band' : config.BAND,
    'a_dict.foo' : config.INT,
    }

def val(which):
    try:
        config.validate(which, test_schema)
        print('Validation: OK')
    except ValueError:
        log.log_exn()
        print('Validation: Error')

print('- expect validation success:')
val(cfg)

print('- unknown item:')
c = copy.deepcopy(cfg)
c['bts'][0]['unknown_item'] = 'no'
val(c)

print('- wrong type modems[].imsi:')
c = copy.deepcopy(cfg)
c['modems'][0]['imsi'] = {'no':'no'}
val(c)

print('- invalid key with space:')
c = copy.deepcopy(cfg)
c['modems'][0]['imsi '] = '12345'
val(c)

print('- list instead of dict:')
c = copy.deepcopy(cfg)
c['a_dict'] = [ 1, 2, 3 ]
val(c)

print('- unknown band:')
c = copy.deepcopy(cfg)
c['bts'][0]['trx'][0]['band'] = 'what'
val(c)

exit(0)

# vim: expandtab tabstop=4 shiftwidth=4
