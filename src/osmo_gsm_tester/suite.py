# osmo_gsm_tester: test suite
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

import os
from . import config, log, template, utils

class Suite(log.Origin):
    '''A test suite reserves resources for a number of tests.
       Each test requires a specific number of modems, BTSs etc., which are
       reserved beforehand by a test suite. This way several test suites can be
       scheduled dynamically without resource conflicts arising halfway through
       the tests.'''

    CONF_FILENAME = 'suite.conf'

    CONF_SCHEMA = {
            'resources.nitb_iface': config.INT,
            'resources.nitb': config.INT,
            'resources.bts': config.INT,
            'resources.msisdn': config.INT,
            'resources.modem': config.INT,
            'defaults.timeout': config.STR,
        }

    class Results:
        def __init__(self):
            self.passed = []
            self.failed = []
            self.all_passed = None

        def add_pass(self, test):
            self.passed.append(test)

        def add_fail(self, test):
            self.failed.append(test)

        def conclude(self):
            self.all_passed = bool(self.passed) and not bool(self.failed)
            return self

    def __init__(self, suite_dir):
        self.set_log_category(log.C_CNF)
        self.suite_dir = suite_dir
        self.set_name(os.path.basename(self.suite_dir))
        self.read_conf()

    def read_conf(self):
        with self:
            if not os.path.isdir(self.suite_dir):
                raise RuntimeError('No such directory: %r' % self.suite_dir)
            self.conf = config.read(os.path.join(self.suite_dir,
                                                 Suite.CONF_FILENAME),
                                    Suite.CONF_SCHEMA)
            self.load_tests()

    def load_tests(self):
        with self:
            self.tests = []
            for basename in os.listdir(self.suite_dir):
                if not basename.endswith('.py'):
                    continue
                self.tests.append(Test(self, basename))

    def add_test(self, test):
        with self:
            if not isinstance(test, Test):
                raise ValueError('add_test(): pass a Test() instance, not %s' % type(test))
            if test.suite is None:
                test.suite = self
            if test.suite is not self:
                raise ValueError('add_test(): test already belongs to another suite')
            self.tests.append(test)

    def run_tests(self):
        results = Suite.Results()
        for test in self.tests:
            self._run_test(test, results)
        return results.conclude()

    def run_tests_by_name(self, *names):
        results = Suite.Results()
        for name in names:
            basename = name
            if not basename.endswith('.py'):
                basename = name + '.py'
            for test in self.tests:
                if basename == test.basename:
                    self._run_test(test, results)
                    break
        return results.conclude()

    def _run_test(self, test, results):
        try:
            with self:
                test.run()
            results.add_pass(test)
        except:
            results.add_fail(test)
            self.log_exn()

class Test(log.Origin):

    def __init__(self, suite, test_basename):
        self.suite = suite
        self.basename = test_basename
        self.set_name(self.basename)
        self.set_log_category(log.C_TST)
        self.path = os.path.join(self.suite.suite_dir, self.basename)
        with self:
            with open(self.path, 'r') as f:
                self.script = f.read()

    def run(self):
        with self:
            self.code = compile(self.script, self.path, 'exec')
            with self.redirect_stdout():
                exec(self.code, self.test_globals())
                self._success = True

    def test_globals(self):
        test_globals = {
            'this': utils.dict2obj({
                    'suite': self.suite.suite_dir,
                    'test': self.basename,
                }),
            'resources': utils.dict2obj({
                }),
        }
        return test_globals

def load(suite_dir):
    return Suite(suite_dir)

# vim: expandtab tabstop=4 shiftwidth=4
