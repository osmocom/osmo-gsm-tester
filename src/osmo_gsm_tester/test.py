# osmo_gsm_tester: context for individual test runs
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

# These will be initialized before each test run.
# A test script can thus establish its context by doing:
# from osmo_gsm_tester.test import *
trial = None
suite = None
test = None
resources = None
log = None
dbg = None
err = None
wait = None
sleep = None
poll = None
prompt = None

def setup(suite_run, _test, ofono_client):
    global trial, suite, test, resources, log, dbg, err, wait, sleep, poll, prompt
    trial = suite_run.trial
    suite = suite_run
    test = _test
    resources = suite_run.reserved_resources
    log = test.log
    dbg = test.dbg
    err = test.err
    wait = suite_run.wait
    sleep = suite_run.sleep
    poll = suite_run.poll
    prompt = suite_run.prompt

# vim: expandtab tabstop=4 shiftwidth=4
