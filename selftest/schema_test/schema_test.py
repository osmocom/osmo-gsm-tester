#!/usr/bin/env python3

import _prep

import sys
import os
import io
import pprint
import copy

from osmo_gsm_tester.core import config, log, schema

def val(which, test_schema):
    try:
        schema.validate(which, test_schema)
        print('Validation: OK')
    except ValueError:
        log.log_exn()
        print('Validation: Error')

def get_case_list(dir):
    li = []
    for f in os.listdir(dir):
        if f.startswith('schema_case'):
            li.append(f)
    return sorted(li)

def test_validator(val):
    return val in ('valid_value1', 'valid_value2')

schema.register_schema_types({'test_type': test_validator,
                              'another_type': lambda val: val == 'unique_val_ok'})


print('==== Testing dynamically generated schemas ====')
for f in get_case_list(_prep.script_dir):
    print('%s:' % f)
    example_config = os.path.join(_prep.script_dir, f)
    cfg = config.read(example_config)
    try:
        schema_def = schema.config_to_schema_def(cfg['schema'], 'foobar.prefix.')
    except AssertionError:
        schema_def = None
        log.log_exn()
        print('config2schema: Error')

    if schema_def is not None:
        pprint.pprint(schema_def)
        i = 0
        for t in cfg['tests']:
            print('validating tests[%d]' % i)
            val(t, schema_def)
            i += 1
    print('----------------------')





# vim: expandtab tabstop=4 shiftwidth=4
