#!/usr/bin/env python3

import tempfile
import os
import sys
import pprint
import shutil
import atexit
import time
import threading
import _prep
from osmo_gsm_tester.core import config, log, util, resource
from osmo_gsm_tester.core.schema import generate_schemas

workdir = util.get_tempdir()

# override config locations to make sure we use only the test conf
config.override_conf = os.path.join(os.path.dirname(sys.argv[0]), 'conf', 'paths.conf')

log.get_process_id = lambda: '123-1490837279'

# Generate supported schemas dynamically from objects:
generate_schemas()

print('- expect solutions:')
pprint.pprint(
    resource.solve([ [0, 1, 2],
                     [0, 1, 2],
                     [0, 1, 2] ]) )
pprint.pprint(
    resource.solve([ [0, 1, 2],
                     [0, 1],
                     [0, 2] ]) ) # == [0, 1, 2]
pprint.pprint(
    resource.solve([ [0, 1, 2],
                     [0],
                     [0, 2] ]) ) # == [1, 0, 2]
pprint.pprint(
    resource.solve([ [0, 1, 2],
                     [2],
                     [0, 2] ]) ) # == [1, 2, 0]

print('- expect failure to solve:')
try:
    resource.solve([ [0, 2],
                     [2],
                     [0, 2] ])
    assert False
except resource.NotSolvable as e:
    print(e)

print('- test removing a Resources list from itself')
try:
    r = resource.Resources({ 'k': [ {'a': 1, 'b': 2}, {'a': 3, 'b': 4}, ],
                             'i': [ {'c': 1, 'd': 2}, {'c': 3, 'd': 4}, ] })
    r.drop(r)
    assert False
except RuntimeError as e:
    print('ok, caused exception RuntimeError: %s' % str(e))

print('- test removing a Resources list from one with the same list in it')
r = resource.Resources({ 'k': [ {'a': 1, 'b': 2}, {'a': 3, 'b': 4}, ],
                         'i': [ {'c': 1, 'd': 2}, {'c': 3, 'd': 4}, ] })
r.drop({ 'k': r.get('k'), 'i': r.get('i') })
assert not r

print('- test resources config and state dir:')
resources_conf = os.path.join(_prep.script_dir, 'resource_test', 'etc',
                              'resources.conf')

state_dir = config.get_state_dir()
rrfile = state_dir.child(resource.RESERVED_RESOURCES_FILE)

pool = resource.ResourcesPool()

print('*** all resources:')
pprint.pprint(pool.all_resources)
print('*** end: all resources\n')

print('- request some resources')
want = {
       'ip_address': [ { 'times': 1 } ],
       'bts': [ { 'type': 'osmo-bts-sysmo', 'times': 1 , 'ciphers': ['a5_1']}, { 'type': 'osmo-bts-trx', 'times': 1 } ],
       'arfcn': [ { 'band': 'GSM-1800', 'times': 2 } ],
       'modem': [ { 'times': 2 , 'ciphers': ['a5_0', 'a5_1']} ],
     }
modifiers = {
    'bts': [ {}, {'num_trx': 2 }],
}
origin = log.Origin(None, 'testowner')

resources = pool.reserve(origin, config.replicate_times(want), config.replicate_times(modifiers))

print('~~~ currently reserved:')
with open(rrfile, 'r') as f:
    print(f.read())
print('~~~ end: currently reserved\n')

print('~~~ with modifiers:')
print(repr(resources))
print('~~~ end: with modifiers:')

resources.free()

print('~~~ currently reserved:')
with open(rrfile, 'r') as f:
    print(f.read())
print('~~~ end: currently reserved\n')

print('- item_matches:')
superset = { 'hello': 'world', 'foo': 'bar', 'ordered_list': [{'xkey': 'xvalue'},{'ykey': 'yvalue'}], 'unordered_list_set': [1, 2, 3]}

subset =  { 'foo': 'bar', 'ordered_list': [{'xkey': 'xvalue'},{'ykey': 'yvalue'}], 'unordered_list_set': [2, 1] }
if resource.item_matches(superset, subset):
    print('1st subset matches correctly, pass')

subset =  { 'ordered_list': [{},{'ykey': 'yvalue'}], 'unordered_list_set': [] }
if resource.item_matches(superset, subset):
    print('2nd subset matches correctly, pass')

subset =  { 'ordered_list': [{'ykey': 'yvalue'}, {'xkey': 'xvalue'}] }
if not resource.item_matches(superset, subset):
    print('3rd subset should not match, pass')

subset =  { 'ordered_list': [{'xkey': 'xvalue'}, {'ykey': 'yvalue'}, {'zkey': 'zvalue'}] }
if not resource.item_matches(superset, subset):
    print('3rd subset should not match, pass')

subset =  { 'unordered_list_set': [4] }
if not resource.item_matches(superset, subset):
    print('4th subset should not match, pass')

print('*** concurrent allocation:')
origin1 = log.Origin(None, 'testowner1')
origin2 = log.Origin(None, 'testowner2')
# We disable dbg() for second thread since FileWatch output result is
# non-deterministic, since sometimes 1 Modiffied event is triggered, sometimes 2.
origin1.dbg = origin2.dbg = lambda obj, *messages, _src=3, **named_items: None
resources2 = None
def second_ogt_instance():
    # should block here until "resources" are freed.
    print('- 2nd instance reserve() start')
    resources2 = pool.reserve(origin2, config.replicate_times(want), config.replicate_times(modifiers))
    print('- 2nd instance reserve() done')
    resources2.free()
resources = pool.reserve(origin1, config.replicate_times(want), config.replicate_times(modifiers))
th = threading.Thread(target=second_ogt_instance)
th.start()
time.sleep(1.0)
print('- 1st instance free()')
resources.free()
th.join()
print('*** end: concurrent allocation')

# vim: expandtab tabstop=4 shiftwidth=4
