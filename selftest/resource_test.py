#!/usr/bin/env python3

import tempfile
import os
import pprint
import shutil
import atexit
import _prep
from osmo_gsm_tester import config, log, resource, util

workdir = util.get_tempdir()

# override config locations to make sure we use only the test conf
config.ENV_CONF = './conf'

log.get_process_id = lambda: '123-1490837279'

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
    print('ok, caused exception: %r' % e)

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
       'bts': [ { 'type': 'sysmo', 'times': 1 }, { 'type': 'oct', 'times': 1 } ],
       'arfcn': [ { 'band': 'GSM-1800', 'times': 2 } ],
       'modem': [ { 'times': 2 } ],
     }

origin = log.Origin(None, 'testowner')

resources = pool.reserve(origin, want)

print('~~~ currently reserved:')
with open(rrfile, 'r') as f:
    print(f.read())
print('~~~ end: currently reserved\n')

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

# vim: expandtab tabstop=4 shiftwidth=4
