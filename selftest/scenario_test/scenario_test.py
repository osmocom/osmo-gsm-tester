#!/usr/bin/env python3

import _prep

import sys
import os
import io
import pprint
import copy

from osmo_gsm_tester.core import schema
from osmo_gsm_tester.core import config
from osmo_gsm_tester.core import scenario

test_schema = {
    'somelist[].somelistitem': schema.STR,
    'anotherlist[]': schema.UINT,
    'foobar' : schema.BOOL_STR,
    }

config.override_conf = os.path.join(os.path.dirname(sys.argv[0]))

def print_scenario(sc):
    # we use copy() to be able to get the dictionary in super class of Scenario:
    pprint.pprint(sc)
    pprint.pprint(sc.copy())

def load_scenario(name, sch=None):
    # Test it loads the same both with .conf and without
    sc = scenario.get_scenario(name, sch)
    print_scenario(sc)
    sc = scenario.get_scenario(name + '.conf', sch)
    print_scenario(sc)
    return sc

# scenario case 01 should load fine
load_scenario('scenario_case_01', test_schema)

# Try loading scenario 1 as if it was parametrized (but it's not):
try:
    sc = scenario.get_scenario('scenario_case_01@', test_schema)
except RuntimeError as e:
    print('OK: expected RuntimeError: %s' % str(e))

# scenario case 02 should fail to load, contains stuff not in test_schema
try:
    sc = scenario.get_scenario('scenario_case_02', test_schema)
except ValueError as e:
    print('OK: expected ValueError')
try:
    sc = scenario.get_scenario('scenario_case_02.conf', test_schema)
except ValueError as e:
    print('OK: expected ValueError')

# scenario case 3 is parametrized, so loading without specifying so should fail:
try:
    sc = scenario.get_scenario('scenario_case_03', test_schema)
except RuntimeError as e:
    print('OK: expected RuntimeError: %s' % str(e))
try:
    sc = scenario.get_scenario('scenario_case_03.conf', test_schema)
except RuntimeError as e:
    print('OK: expected RuntimeError: %s' % str(e))

#scenario 3 should load fine this way:
sc = load_scenario('scenario_case_03@heyho,1,yes', test_schema)

#scenario 3 should fail due to missing parameters:
try:
    sc = scenario.get_scenario('scenario_case_03@heyho,1', test_schema)
except NameError as e:
    print('OK: expected NameError: %s' % str(e))
try:
    sc = scenario.get_scenario('scenario_case_03@heyho,1.conf', test_schema)
except NameError as e:
    print('OK: expected NameError: %s' % str(e))

#scenario 3 should load the specific config file this way:
sc = load_scenario('scenario_case_03@specific', test_schema)

# vim: expandtab tabstop=4 shiftwidth=4
