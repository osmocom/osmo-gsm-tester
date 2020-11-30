#!/usr/bin/env python3
import _prep

from osmo_gsm_tester.obj.osmo_ctrl import *

rc = RateCounters()
print('- empty RateCounters()' + rc.str())

rc = RateCounters('inst', 'var')
print('- initialized RateCounters, single var' + rc.str())
rc.inc('inst', 'var')
print('- incremented inst.var' + rc.str())
rc.inc('inst', 'var')
print('- incremented inst.var again' + rc.str())
rc.inc('inst', 'var', 5)
print('- incremented inst.var by 5' + rc.str())

rc = RateCounters('inst', ('foo', 'var'))
print('- initialized RateCounters, two vars' + rc.str())
rc.inc('inst', ('foo', 'var'))
print('- incremented foo and var' + rc.str())
rc.inc('inst', 'var')
print('- incremented var again' + rc.str())
rc.inc('inst', 'foo', 5)
print('- incremented foo by 5' + rc.str())

rc = RateCounters('inst', ('foo', 'var'), instances=range(3))
print('- initialized RateCounters, two vars, three instances' + rc.str())
rc.inc('inst', 'foo', instances=0)
rc.inc('inst', 'var', instances=1)
print('- incremented foo and var on separate instances' + rc.str())
rc.inc('inst', 'var', instances=2)
print('- incremented var on instance 2' + rc.str())
rc.inc('inst', 'foo', 5, instances=(1,2))
print('- incremented foo by 5 on instances 1,2' + rc.str())

rc_rel = rc.copy()
print('- copy' + rc_rel.str())
rc.inc('inst', ('foo', 'var'), 100, instances=range(3))
print('- increment two vars by 100 on all three instances' + rc.str())
rc.subtract(rc_rel)
print('- subtract original copy' + rc.str())
rc.add(rc_rel)
print('- add original copy' + rc.str())

rc.inc('inst', ('foo', 'var', 'moo'), 23, instances=range(3), kinds=('per_hour', 'per_day'))
print('- increment types per_hour, per_day by 23' + rc.str())

rc2 = rc.copy()
print('- copy' + rc2.str())
print('- match? ', (rc == rc2))
rc2.inc('inst', 'foo')
print('- increment foo' + rc2.str())
print('- match? ', (rc == rc2))

# vim: expandtab tabstop=4 shiftwidth=4
