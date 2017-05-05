#!/usr/bin/env python3

# osmo_gsm_tester: logging tests
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import _prep

import sys
import os

from osmo_gsm_tester import log

#log.targets[0].get_time_str = lambda: '01:02:03'
fake_time = '01:02:03'
log.style_change(time=True, time_fmt=fake_time)
log.set_all_levels(None)

print('- Testing global log functions')
log.log('<origin>', log.C_TST, 'from log.log()')
log.dbg('<origin>', log.C_TST, 'from log.dbg(), not seen')
log.set_level(log.C_TST, log.L_DBG)
log.dbg('<origin>', log.C_TST, 'from log.dbg()')
log.set_level(log.C_TST, log.L_LOG)
log.err('<origin>', log.C_TST, 'from log.err()')

print('- Testing log.Origin functions')
class LogTest(log.Origin):
    pass

t = LogTest()
t.set_log_category(log.C_TST)
t.set_name('some', 'name', some="detail")
	
t.log("hello log")
t.err("hello err")
t.dbg("hello dbg not visible")

t.log("message", int=3, tuple=('foo', 42), none=None, str='str\n')

log.set_level(log.C_TST, log.L_DBG)
t.dbg("hello dbg")

print('- Testing log.style()')

log.style(time=True, category=False, level=False, origin=False, src=False, time_fmt=fake_time)
t.dbg("only time")
log.style(time=False, category=True, level=False, origin=False, src=False, time_fmt=fake_time)
t.dbg("only category")
log.style(time=False, category=False, level=True, origin=False, src=False, time_fmt=fake_time)
t.dbg("only level")
log.style(time=False, category=False, level=False, origin=True, src=False, time_fmt=fake_time)
t.dbg("only origin")
log.style(time=False, category=False, level=False, origin=False, src=True, time_fmt=fake_time)
t.dbg("only src")

print('- Testing log.style_change()')
log.style(time=False, category=False, level=False, origin=False, src=False, time_fmt=fake_time)
t.dbg("no log format")
log.style_change(time=True)
t.dbg("add time")
log.style_change(time=True, time_fmt=0)
t.dbg("but no time format")
log.style_change(time=True, time_fmt=fake_time)
log.style_change(level=True)
t.dbg("add level")
log.style_change(category=True)
t.dbg("add category")
log.style_change(src=True)
t.dbg("add src")
log.style_change(origin=True)
t.dbg("add origin")

print('- Testing origin_width')
t = LogTest()
t.set_log_category(log.C_TST)
t.set_name('shortname')
log.style(origin_width=23, time_fmt=fake_time)
t.log("origin str set to 23 chars")
t.set_name('very long name', some='details', and_some=(3, 'things', 'in a tuple'))
t.log("long origin str")
t.dbg("long origin str dbg")
t.err("long origin str err")

print('- Testing log.Origin with omitted info')
t = LogTest()
t.set_log_category(log.C_TST)
t.log("hello log, name implicit from class name")

t = LogTest()
t.set_name('explicit_name')
t.log("hello log, no category set")

t = LogTest()
t.log("hello log, no category nor name set")
t.dbg("hello log, no category nor name set, not seen")
log.set_level(log.C_DEFAULT, log.L_DBG)
t.dbg("debug message, no category nor name set")

print('- Testing logging of Exceptions, tracing origins')
log.style(time_fmt=fake_time, origin_width=0)

class Thing(log.Origin):
    def __init__(self, some_path):
        self.set_log_category(log.C_TST)
        self.set_name(some_path)

    def say(self, msg):
        print(msg)

#log.style_change(trace=True)

with Thing('print_redirected'):
    print("Not throwing an exception in 'with:' works.")

def l1():
    level1 = Thing('level1')
    with level1:
        l2()

def l2():
    level2 = Thing('level2')
    with level2:
        l3(level2)

def l3(level2):
    level3 = Thing('level3')
    with level3:
        print('nested print just prints')
        level3.log('nested log()')
        level2.log('nested l2 log() from within l3 scope')
        raise ValueError('bork')

try:
    l1()
except Exception:
    log.log_exn()

print('- Enter the same Origin context twice')
with Thing('level1'):
    l2 = Thing('level2')
    with l2:
        with l2:
            l2.log('nested log')

# vim: expandtab tabstop=4 shiftwidth=4
