# osmo_gsm_tester: report: directory of binaries to be tested
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Pau Espin Pedrol <pespin@sysmocom.de>
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

import os
import math
from datetime import datetime
import xml.etree.ElementTree as et
from . import log, suite

def trial_to_junit_write(trial, junit_path):
    elements = et.ElementTree(element=trial_to_junit(trial))
    elements.write(junit_path)

def trial_to_junit(trial):
    testsuites = et.Element('testsuites')
    for suite in trial.suites:
        testsuite = suite_to_junit(suite)
        testsuites.append(testsuite)
    return testsuites

def suite_to_junit(suite):
    testsuite = et.Element('testsuite')
    testsuite.set('name', suite.name())
    testsuite.set('hostname', 'localhost')
    testsuite.set('timestamp', datetime.fromtimestamp(round(suite.start_timestamp)).isoformat())
    testsuite.set('time', str(math.ceil(suite.duration)))
    testsuite.set('tests', str(len(suite.tests)))
    testsuite.set('failures', str(suite.test_failed_ctr))
    for test in suite.tests:
        testcase = test_to_junit(test)
        testsuite.append(testcase)
    return testsuite

def test_to_junit(test):
    testcase = et.Element('testcase')
    testcase.set('name', test.name())
    testcase.set('time', str(math.ceil(test.duration)))
    if test.status == suite.Test.SKIP:
        skip = et.SubElement(testcase, 'skipped')
    elif test.status == suite.Test.FAIL:
            failure = et.SubElement(testcase, 'failure')
            failure.set('type', test.fail_type)
            failure.text = test.fail_message
    return testcase

def trial_to_text(trial):
    msg =  '\n%s [%s]\n  ' % (trial.status, trial.name())
    msg += '\n  '.join(suite_to_text(result) for result in trial.suites)
    return msg

def suite_to_text(suite):
    if suite.test_failed_ctr:
        return 'FAIL: [%s] %d failed out of %d tests run (%d skipped):\n    %s' % (
               suite.name(), suite.test_failed_ctr, len(suite.tests), suite.test_skipped_ctr,
               '\n    '.join([test_to_text(t) for t in suite.tests]))
    if not suite.tests:
        return 'no tests were run.'
    return 'pass: all %d tests passed (%d skipped).' % (len(suite.tests), suite.test_skipped_ctr)

def test_to_text(test):
    ret = "%s: [%s]" % (test.status, test.name())
    if test.status != suite.Test.SKIP:
        ret += " (%s, %d sec)" % (datetime.fromtimestamp(round(test.start_timestamp)).isoformat(), test.duration)
    if test.status == suite.Test.FAIL:
        ret += " type:'%s' message: %s" % (test.fail_type, test.fail_message.replace('\n', '\n        '))
    return ret

# vim: expandtab tabstop=4 shiftwidth=4
