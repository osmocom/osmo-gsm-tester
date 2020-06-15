#!/usr/bin/env python3
import _prep

from osmo_gsm_tester.core import report
from osmo_gsm_tester.core import log
from osmo_gsm_tester.core import util
from osmo_gsm_tester.core import test
from osmo_gsm_tester.core import suite
from osmo_gsm_tester.core import config

import os
import sys
import shutil
import difflib
import xml.etree.ElementTree as et

class FakeTrial(log.Origin):
    def __init__(self):
        super().__init__(log.C_TST, 'trial')
        self.dir = util.Dir(example_trial_dir)
        self._run_dir = None
        self.suites = []

    def get_all_inst_hash_info(self):
        return { 'foobar/potato': '1234', 'orange': 'abcd' }

    def get_run_dir(self):
        if self._run_dir is not None:
            return self._run_dir
        self._run_dir = util.Dir(self.dir.new_child('test_run'))
        self._run_dir.mkdir()
        return self._run_dir

class FakeSuiteDefinition(log.Origin):
        def __init__(self, name, num_tests):
            super().__init__(log.C_TST, name)
            self.test_basenames = [name + '-' + str(tid) for tid in range(num_tests) ]
            self.conf = {}
            self.suite_dir = util.Dir(example_trial_dir).new_child('suitedef' + name)


def fake_run_test(test_obj, status, duration, sysout=None, kpis=None):
    test_obj.status = status
    test_obj.duration = duration
    if sysout is not None:
        test_obj.set_report_stdout(sysout)
    if kpis is not None:
        test_obj.set_kpis(kpis)
    if status == test.Test.FAIL:
        test_obj.fail_type = 'fake_fail_type'
        test_obj.fail_message = 'fake_fail_message'
        test_obj.fail_tb = 'system stderr fake content'

def fake_run_suite(suite_obj, duration):
    suite_obj.duration = duration
    suite_obj.determine_status()

config.override_conf = os.path.join(os.path.dirname(sys.argv[0]), 'main.conf')

example_trial_dir = os.path.join('test_trial_tmp')

trial = FakeTrial()

# Suite passes with 2 tests passing
s_def = FakeSuiteDefinition('suiteA', 2)
s = suite.SuiteRun(trial, s_def.name(), s_def)
trial.suites.append(s)
fake_run_test(s.tests[0], test.Test.PASS, 30)
fake_run_test(s.tests[1], test.Test.PASS, 10, 'yay this is a test-applied stdout')
#fake_run_test(suiteA.tests[0], test.Test.UNKNOWN, 20)
fake_run_suite(s, 50)

# Suite passes first test but next ones are not ececuted
s_def = FakeSuiteDefinition('suiteB', 3)
s = suite.SuiteRun(trial, s_def.name(), s_def)
trial.suites.append(s)
fake_run_test(s.tests[0], test.Test.PASS, 10)
fake_run_suite(s, 20)

# Suite passes one test selected, others are skipped
s_def = FakeSuiteDefinition('suiteC', 3)
s = suite.SuiteRun(trial, s_def.name(), s_def)
trial.suites.append(s)
s.tests[0].set_skip()
fake_run_test(s.tests[1], test.Test.PASS, 10)
s.tests[2].set_skip()
fake_run_suite(s, 12)

# Suite fails due to one of its tests failing
s_def = FakeSuiteDefinition('suiteD', 2)
s = suite.SuiteRun(trial, s_def.name(), s_def)
trial.suites.append(s)
fake_run_test(s.tests[0], test.Test.FAIL, 12)
fake_run_test(s.tests[1], test.Test.PASS, 10)
fake_run_suite(s, 20)

# Test adding KPIs
s_def = FakeSuiteDefinition('suiteE', 2)
s = suite.SuiteRun(trial, s_def.name(), s_def)
trial.suites.append(s)
fake_run_test(s.tests[0], test.Test.FAIL, 12, kpis={'ueA': {'kpiA': 30, 'kpiB': 'foobar', 'yet-another-level': {'foo': 'bar'}}, 'enbD': {'foobar-boolean': True }, 'somekpi': 'someval'})
fake_run_test(s.tests[1], test.Test.PASS, 10, kpis={'abcd': 'abcdval'})
fake_run_suite(s, 20)

element = report.trial_to_junit(trial)

def indent(elem, level=0):
    i = "\n" + level*"  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level+1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

def udiff(expect, got, expect_path):
    expect = expect.splitlines(1)
    got =  got.splitlines(1)
    for line in difflib.unified_diff(expect, got,
                                     fromfile=expect_path, tofile='got'):
        sys.stderr.write(line)
        if not line.endswith('\n'):
            sys.stderr.write('[no-newline]\n')

indent(element)
#canonicalize() is only available in python3.8+, and we need it to have reliable string output:
if hasattr(et, 'canonicalize'):
    got = et.canonicalize(et.tostring(element)).rstrip()
    exp_path = os.path.join(os.path.dirname(sys.argv[0]), 'expected_junit_output.xml')
    with open(exp_path, 'r') as f:
        exp = f.read().rstrip()
    udiff(exp, got, exp_path)
    # Uncomment to update exp_path:
    #with open(exp_path, 'w') as f:
    #    f.write(got)

#deleting generated tmp trial dir:
shutil.rmtree(example_trial_dir, ignore_errors=True)

# vim: expandtab tabstop=4 shiftwidth=4
