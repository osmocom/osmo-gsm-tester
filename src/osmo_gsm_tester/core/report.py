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

# junit xml format: https://llg.cubic.org/docs/junit/

import math
import sys
import re
from datetime import datetime
import xml.etree.ElementTree as et
from xml.sax.saxutils import escape
from . import test

invalid_xml_char_ranges = [(0x00, 0x08), (0x0B, 0x0C), (0x0E, 0x1F), (0x7F, 0x84),
                    (0x86, 0x9F), (0xFDD0, 0xFDDF), (0xFFFE, 0xFFFF)]
if sys.maxunicode >= 0x10000:  # not narrow build
    invalid_xml_char_ranges.extend([(0x1FFFE, 0x1FFFF), (0x2FFFE, 0x2FFFF),
                             (0x3FFFE, 0x3FFFF), (0x4FFFE, 0x4FFFF),
                             (0x5FFFE, 0x5FFFF), (0x6FFFE, 0x6FFFF),
                             (0x7FFFE, 0x7FFFF), (0x8FFFE, 0x8FFFF),
                             (0x9FFFE, 0x9FFFF), (0xAFFFE, 0xAFFFF),
                             (0xBFFFE, 0xBFFFF), (0xCFFFE, 0xCFFFF),
                             (0xDFFFE, 0xDFFFF), (0xEFFFE, 0xEFFFF),
                             (0xFFFFE, 0xFFFFF), (0x10FFFE, 0x10FFFF)])
invalid_xml_char_ranges_str = ['%s-%s' % (chr(low), chr(high))
                   for (low, high) in invalid_xml_char_ranges]
invalid_xml_char_ranges_regex = re.compile('[%s]' % ''.join(invalid_xml_char_ranges_str))
ansi_color_re = re.compile('\033[0-9;]{1,4}m')

def escape_xml_invalid_characters(str):
    replacement_char = '\uFFFD' # Unicode replacement character
    return invalid_xml_char_ranges_regex.sub(replacement_char, escape(str))

def strip_ansi_colors(text):
    return ''.join(ansi_color_re.split(text))

def hash_info_to_junit(testsuite, hash_info):
    properties = et.SubElement(testsuite, 'properties')
    for key, val in hash_info.items():
        prop = et.SubElement(properties, 'property')
        prop.set('name', 'ref:' + key)
        prop.set('value', val)

def dict_to_junit(parent, d):
    for key, val in d.items():
        if isinstance(val, dict):
            node = et.SubElement(parent, 'kpi_node')
            node.set('name', key)
            dict_to_junit(node, val)
            continue
        if isinstance(val, (tuple, list)):
            node = et.SubElement(parent, 'kpi_node')
            node.set('name', key)
            list_to_junit(node, val)
            continue
        # scalar:
        node = et.SubElement(parent, 'property')
        node.set('name', key)
        node.set('value', str(val))

def list_to_junit(parent, li):
    for i in range(len(li)):
        if isinstance(li[i], dict):
            node = et.SubElement(parent, 'kpi_node')
            node.set('name', str(i))
            dict_to_junit(node, li[i])
            continue
        if isinstance(val, (tuple, list)):
            node = et.SubElement(parent, 'kpi_node')
            node.set('name', str(i))
            list_to_junit(node, li[i])
            continue
        # scalar:
        node = et.SubElement(parent, 'property')
        node.set('name', str(i))
        node.set('value', str(li[i]))

def kpis_to_junit(parent, kpis):
    if not kpis:
        return
    assert isinstance(kpis, dict)
    knode = et.SubElement(parent, 'kpis')
    dict_to_junit(knode, kpis)

def trial_to_junit_write(trial, junit_path):
    elements = et.ElementTree(element=trial_to_junit(trial))
    elements.write(junit_path)

def trial_to_junit(trial):
    testsuites = et.Element('testsuites')
    num_tests = 0
    num_failures = 0
    num_errors = 0
    time = 0
    id = 0
    hash_info = trial.get_all_inst_hash_info()
    for suite in trial.suites:
        testsuite = suite_to_junit(suite)
        hash_info_to_junit(testsuite, hash_info)
        testsuite.set('id', str(id))
        id += 1
        testsuites.append(testsuite)
        num_tests += int(testsuite.get('tests'))
        num_failures += int(testsuite.get('failures'))
        num_errors += int(testsuite.get('errors'))
        time += suite.duration
    testsuites.set('tests', str(num_tests))
    testsuites.set('errors', str(num_errors))
    testsuites.set('failures', str(num_failures))
    testsuites.set('time', str(math.ceil(time)))
    testsuites.set('name', trial.name())
    return testsuites

def suite_to_junit(suite):
    testsuite = et.Element('testsuite')
    testsuite.set('name', suite.name())
    testsuite.set('hostname', 'localhost')
    if suite.start_timestamp:
        testsuite.set('timestamp', datetime.fromtimestamp(round(suite.start_timestamp)).isoformat())
        testsuite.set('time', str(math.ceil(suite.duration)))
    testsuite.set('tests', str(len(suite.tests)))
    passed, skipped, failed, errors = suite.count_test_results()
    for suite_test in suite.tests:
        testcase = test_to_junit(suite_test)
        testcase.set('classname', suite.name())
        testsuite.append(testcase)

        for report_fragment in suite_test.report_fragments:
            full_name = '%s/%s' % (suite_test.name(), report_fragment.name)
            el = et.Element('testcase')
            el.set('name', full_name)
            el.set('time', str(math.ceil(report_fragment.duration)))
            if report_fragment.result == test.Test.SKIP:
                et.SubElement(el, 'skipped')
                skipped += 1
            elif report_fragment.result == test.Test.FAIL:
                failure = et.SubElement(el, 'failure')
                failure.set('type', suite_test.fail_type or 'failure')
                failed += 1
            elif report_fragment.result != test.Test.PASS:
                error = et.SubElement(el, 'error')
                error.text = 'could not run'
                errors += 1

            if report_fragment.output:
                sout = et.SubElement(el, 'system-out')
                sout.text = escape_xml_invalid_characters(strip_ansi_colors(report_fragment.output))
            testsuite.append(el)

    testsuite.set('errors', str(errors))
    testsuite.set('failures', str(failed))
    testsuite.set('skipped', str(skipped))
    testsuite.set('disabled', str(skipped))
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
    kpis_to_junit(testcase, t.kpis())
    sout = et.SubElement(testcase, 'system-out')
    sout.text = escape_xml_invalid_characters(t.report_stdout())
    return testcase

def trial_to_text(trial):
    suite_passes = []
    suite_failures = []
    count_fail = 0
    count_pass = 0
    for suite in trial.suites:
        if suite.passed():
            count_pass += 1
            suite_passes.append(suite_to_text(suite))
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
    msg.extend(suite_passes)
    return '\n'.join(msg)

def suite_to_text(suite):
    if not suite.tests:
        return 'no tests were run.'

    passed, skipped, failed, errors = suite.count_test_results()
    details = []
    if failed:
        details.append('fail: %d' % failed)
    if errors:
        details.append('errors: %d' % errors)
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
