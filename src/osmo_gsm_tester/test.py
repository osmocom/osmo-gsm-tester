# osmo_gsm_tester: test class
#
# Copyright (C) 2017 by sysmocom - s.f.m.c. GmbH
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

import os
import sys
import time
import traceback
from . import testenv

from . import log, util, resource

class Test(log.Origin):
    UNKNOWN = 'UNKNOWN'
    SKIP = 'skip'
    PASS = 'pass'
    FAIL = 'FAIL'

    _run_dir = None

    def __init__(self, suite_run, test_basename):
        self.basename = test_basename
        super().__init__(log.C_TST, self.basename)
        self.suite_run = suite_run
        self.path = os.path.join(self.suite_run.definition.suite_dir, self.basename)
        self.status = Test.UNKNOWN
        self.start_timestamp = 0
        self.duration = 0
        self.fail_type = None
        self.fail_message = None

    def get_run_dir(self):
        if self._run_dir is None:
            self._run_dir = util.Dir(self.suite_run.get_run_dir().new_dir(self._name))
        return self._run_dir

    def run(self):
        try:
            log.large_separator(self.suite_run.trial.name(), self.suite_run.name(), self.name(), sublevel=3)
            self.status = Test.UNKNOWN
            self.start_timestamp = time.time()
            from . import suite, sms
            from .event_loop import MainLoop
            testenv.setup(self.suite_run, self, suite, MainLoop, sms)
            with self.redirect_stdout():
                util.run_python_file('%s.%s' % (self.suite_run.definition.name(), self.basename),
                                     self.path)
            if self.status == Test.UNKNOWN:
                 self.set_pass()
        except Exception as e:
            if hasattr(e, 'msg'):
                msg = e.msg
            else:
                msg = str(e)
            if isinstance(e, AssertionError):
                # AssertionError lacks further information on what was
                # asserted. Find the line where the code asserted:
                msg += log.get_src_from_exc_info(sys.exc_info())
            # add source file information to failure report
            if hasattr(e, 'origins'):
                msg += ' [%s]' % e.origins
            tb_str = traceback.format_exc()
            if isinstance(e, resource.NoResourceExn):
                tb_str += self.suite_run.resource_status_str()
            self.set_fail(type(e).__name__, msg, tb_str, log.get_src_from_exc_info())
        except BaseException as e:
            # when the program is aborted by a signal (like Ctrl-C), escalate to abort all.
            self.err('TEST RUN ABORTED: %s' % type(e).__name__)
            raise

    def name(self):
        l = log.get_line_for_src(self.path)
        if l is not None:
            return '%s:%s' % (self._name, l)
        return super().name()

    def set_fail(self, fail_type, fail_message, tb_str=None, src=4):
        self.status = Test.FAIL
        self.duration = time.time() - self.start_timestamp
        self.fail_type = fail_type
        self.fail_message = fail_message

        if tb_str is None:
            # populate an exception-less call to set_fail() with traceback info
            tb_str = ''.join(traceback.format_stack()[:-1])

        self.fail_tb = tb_str
        self.err('%s: %s' % (self.fail_type, self.fail_message), _src=src)
        if self.fail_tb:
            self.log(self.fail_tb, _level=log.L_TRACEBACK)
        self.log('Test FAILED (%.1f sec)' % self.duration)

    def set_pass(self):
        self.status = Test.PASS
        self.duration = time.time() - self.start_timestamp
        self.log('Test passed (%.1f sec)' % self.duration)

    def set_skip(self):
        self.status = Test.SKIP
        self.duration = 0

# vim: expandtab tabstop=4 shiftwidth=4
