# osmo_gsm_tester: report: directory of binaries to be tested
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Pau Espin Pedrol <pespin@sysmocom.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import math
from datetime import datetime
import xml.etree.ElementTree as et
from . import test

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
    if suite.start_timestamp:
        testsuite.set('timestamp', datetime.fromtimestamp(round(suite.start_timestamp)).isoformat())
        testsuite.set('time', str(math.ceil(suite.duration)))
    testsuite.set('tests', str(len(suite.tests)))
    testsuite.set('failures', str(suite.count_test_results()[2]))
    for test in suite.tests:
        testcase = test_to_junit(test)
        testsuite.append(testcase)
    return testsuite

def test_to_junit(t):
    testcase = et.Element('testcase')
    testcase.set('name', t.name())
    testcase.set('time', str(math.ceil(t.duration)))
    if t.status == test.Test.SKIP:
        et.SubElement(testcase, 'skipped')
    elif t.status == test.Test.FAIL:
        failure = et.SubElement(testcase, 'failure')
        failure.set('type', t.fail_type or 'failure')
        failure.text = t.fail_message
        if t.fail_tb:
            system_err = et.SubElement(testcase, 'system-err')
            system_err.text = t.fail_tb
    elif t.status != test.Test.PASS:
        error = et.SubElement(testcase, 'error')
        error.text = 'could not run'
    return testcase

def trial_to_text(trial):
    suite_failures = []
    count_fail = 0
    count_pass = 0
    for suite in trial.suites:
        if suite.passed():
            count_pass += 1
        else:
            count_fail += 1
            suite_failures.append(suite_to_text(suite))

    summary = ['%s: %s' % (trial.name(), trial.status)]
    if count_fail:
        summary.append('%d suites failed' % count_fail)
    if count_pass:
        summary.append('%d suites passed' % count_pass)
    msg = [', '.join(summary)]
    msg.extend(suite_failures)
    return '\n'.join(msg)

def suite_to_text(suite):
    if not suite.tests:
        return 'no tests were run.'

    passed, skipped, failed = suite.count_test_results()
    details = []
    if failed:
        details.append('fail: %d' % failed)
    if passed:
        details.append('pass: %d' % passed)
    if skipped:
        details.append('skip: %d' % skipped)
    msgs = ['%s: %s (%s)' % (suite.status, suite.name(), ', '.join(details))]
    msgs.extend([test_to_text(t) for t in suite.tests])
    return '\n    '.join(msgs)

def test_to_text(t):
    msgs = ['%s: %s' % (t.status, t.name())]
    if t.start_timestamp:
        msgs.append('(%.1f sec)' % t.duration)
    if t.status == test.Test.FAIL:
        msgs.append('%s: %s' % (t.fail_type, t.fail_message))
    return ' '.join(msgs)

# vim: expandtab tabstop=4 shiftwidth=4
