#!/usr/bin/env python3

import _prep

import sys
import os
import io
import pprint
import copy

from osmo_gsm_tester import config, log, schema

example_config_file = 'test.cfg'
example_config = os.path.join(_prep.script_dir, 'config_test', example_config_file)
cfg = config.read(example_config)

pprint.pprint(cfg, width=81)

test_schema = {
    'modems[].dbus_path': schema.STR,
    'modems[].msisdn': schema.STR,
    'modems[].imsi': schema.IMSI,
    'modems[].ki': schema.STR,
    'bts[].name' : schema.STR,
    'bts[].type' : schema.STR,
    'bts[].addr' : schema.STR,
    'bts[].trx[].timeslots[]' : schema.STR,
    'bts[].trx[].band' : schema.BAND,
    'a_dict.foo' : schema.INT,
    'addr[]' : schema.IPV4,
    'hwaddr[]' : schema.HWADDR,
    'imsi[]' : schema.IMSI,
    'ki[]' : schema.KI,
    }

def val(which):
    try:
        schema.validate(which, test_schema)
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

print('- invalid v4 addrs:')
c = copy.deepcopy(cfg)
c['addr'][3] = '1.2.3'
val(c)
c['addr'][3] = '1.2.3 .4'
val(c)
c['addr'][3] = '91.2.3'
val(c)
c['addr'][3] = 'go away'
val(c)
c['addr'][3] = ''
val(c)
c['addr'][3] = None
val(c)

print('- invalid hw addrs:')
c = copy.deepcopy(cfg)
c['hwaddr'][3] = '1.2.3'
val(c)
c['hwaddr'][3] = '0b:0c:0d:0e:0f:0g'
val(c)
c['hwaddr'][3] = '0b:0c:0d:0e : 0f:0f'
val(c)
c['hwaddr'][3] = 'go away'
val(c)
c['hwaddr'][3] = ''
val(c)
c['hwaddr'][3] = None
val(c)

print('- invalid imsis:')
c = copy.deepcopy(cfg)
c['imsi'][2] = '99999999x9'
val(c)
c['imsi'][2] = '123 456 789 123'
val(c)
c['imsi'][2] = 'go away'
val(c)
c['imsi'][2] = ''
val(c)
c['imsi'][2] = None
val(c)

print('- Combine dicts:')
a = {'times': '2'}
b = {'type': 'osmo-bts-trx'}
res = {'times': '2', 'type': 'osmo-bts-trx'}
config.combine(a, b)
assert a == res

print('- Combine dicts 2:')
a = {'times': '1', 'label': 'foo', 'type': 'osmo-bts-trx'}
b = {'type': 'osmo-bts-trx'}
res = {'times': '1', 'label': 'foo', 'type': 'osmo-bts-trx'}
config.combine(a, b)
assert a == res

print('- Combine lists:')
a = { 'a_list': ['x', 'y', 'z'] }
b = { 'a_list': ['y'] }
res = {'a_list': ['x', 'y', 'z']}
config.combine(a, b)
assert a == res

print('- Combine lists 2:')
a = { 'a_list': ['x'] }
b = { 'a_list': ['w', 'u', 'x', 'y', 'z'] }
res = {'a_list': ['x', 'w', 'u', 'y', 'z']}
config.combine(a, b)
assert a == res

print('- Combine lists 3:')
a = { 'a_list': ['x', 3] }
b = { 'a_list': ['y', 'z'] }
try:
    config.combine(a, b)
except ValueError:
    print("ValueError expected")

print('- Combine lists 4:')
a = { 'a_list': [2, 3] }
b = { 'a_list': ['y', 'z'] }
try:
    config.combine(a, b)
except ValueError:
    print("ValueError expected")

print('- Combine lists 5:')
a = { 'a_list': [{}, {}] }
b = { 'a_list': ['y', 'z'] }
try:
    config.combine(a, b)
except ValueError:
    print("ValueError expected")

print('- Combine lists 6:')
a = { 'a_list': [{}, {}] }
b = { 'a_list': [{}] }
res = {'a_list': [{}, {}]}
config.combine(a, b)
assert a == res

print('- Combine lists 7:')
a = { 'times': '1', 'label': 'foo', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}] }
b = { 'type': 'osmo-bts-trx', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}] }
res = {'times': '1', 'label': 'foo', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}], 'type': 'osmo-bts-trx'}
config.combine(a, b)
assert a == res

print('- Combine lists 8:')
a = { 'times': '1', 'label': 'foo', 'trx': [{'nominal power': '10'}] }
b = { 'type': 'osmo-bts-trx', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}] }
res = {'times': '1', 'label': 'foo', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}], 'type': 'osmo-bts-trx'}
config.combine(a, b)
assert a == res

print('- Combine lists 9:')
a = { 'times': '1', 'label': 'foo', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}] }
b = { 'type': 'osmo-bts-trx', 'trx': [{'nominal power': '10'}] }
res = {'times': '1', 'label': 'foo', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}], 'type': 'osmo-bts-trx'}
config.combine(a, b)
assert a == res

print('- Combine lists 10:')
a = { 'times': '1', 'label': 'foo', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}] }
b = { 'type': 'osmo-bts-trx', 'trx': [{}, {'nominal power': '12'}] }
res = {'times': '1', 'label': 'foo', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}], 'type': 'osmo-bts-trx'}
config.combine(a, b)
assert a == res

print('- Combine lists 13:')
a = { 'times': '1', 'label': 'foo', 'trx': [{}, {'nominal power': '12'}] }
b = { 'type': 'osmo-bts-trx', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}] }
res = {'times': '1', 'label': 'foo', 'trx': [{'nominal power': '10'}, {'nominal power': '12'}], 'type': 'osmo-bts-trx'}
config.combine(a, b)
assert a == res

print('- Combine lists 14:')
a = { 'times': '1', 'label': 'foo', 'trx': [] }
b = { 'type': 'osmo-bts-trx', 'trx': [] }
res = {'times': '1', 'label': 'foo', 'trx': [], 'type': 'osmo-bts-trx'}
config.combine(a, b)
assert a == res

# vim: expandtab tabstop=4 shiftwidth=4
