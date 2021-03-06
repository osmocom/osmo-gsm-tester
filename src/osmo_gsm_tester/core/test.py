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

from . import log
from . import  util
from . import resource
from .event_loop import MainLoop

from .. import testenv

class Test(log.Origin):
    UNKNOWN = 'UNKNOWN' # matches junit 'error'
    SKIP = 'skip'
    PASS = 'pass'
    FAIL = 'FAIL'

    def __init__(self, suite_run, test_basename, config_test_specific):
        self.basename = test_basename
        super().__init__(log.C_TST, self.basename)
        self._run_dir = None
        self.suite_run = suite_run
        self._config_test_specific = config_test_specific
        self.path = os.path.join(self.suite_run.definition.suite_dir, self.basename)
        self.status = Test.UNKNOWN
        self.report_fragments = []
        self.start_timestamp = 0
        self.duration = 0
        self.fail_type = None
        self.fail_message = None
        self.log_targets = []
        self._report_stdout = None
        self._kpis = None
        self.timeout = int(config_test_specific['timeout']) if 'timeout' in config_test_specific else None

    def module_name(self):
        'Return test name without trailing .py'
        assert self.basename.endswith('.py')
        return self.basename[:-3]

    def get_run_dir(self):
        if self._run_dir is None:
            self._run_dir = util.Dir(self.suite_run.get_run_dir().new_dir(self._name))
        return self._run_dir

    def run(self):
        testenv_obj = None
        try:
            self.log_targets = [log.FileLogTarget(self.get_run_dir().new_child(log.FILE_LOG)).set_all_levels(log.L_DBG).style_change(trace=True),
                                log.FileLogTarget(self.get_run_dir().new_child(log.FILE_LOG_BRIEF)).style_change(src=False, all_origins_on_levels=(log.L_ERR, log.L_TRACEBACK))]
            log.large_separator(self.suite_run.trial().name(), self.suite_run.name(), self.name(), sublevel=3)
            self.status = Test.UNKNOWN
            self.start_timestamp = time.time()
            testenv_obj = testenv.setup(self.suite_run, self)
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
        finally:
            if testenv_obj:
                testenv_obj.stop()
            for log_tgt in self.log_targets:
                log_tgt.remove()

    def src(self):
        l = log.get_line_for_src(self.path)
        if l is not None:
            return '%s:%s' % (self.name(), l)
        return self.name()

    def elapsed_time(self):
        'time elapsed since test was started'
        return time.time() - self.start_timestamp

    def set_fail(self, fail_type, fail_message, tb_str=None, src=4):
        self.status = Test.FAIL
        self.duration = self.elapsed_time()
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
        self.duration = self.elapsed_time()
        self.log('Test passed (%.1f sec)' % self.duration)

    def set_skip(self):
        self.status = Test.SKIP
        self.duration = 0

    def config_test_specific(self):
        return self._config_test_specific

    def set_kpis(self, kpis):
        if not isinstance(kpis, dict):
            raise log.Error('Expected dictionary in toplevel kpis')
        if isinstance(self._kpis, dict):
            self._kpis.update(kpis)
        else:
            self._kpis = kpis

    def kpis(self):
        return self._kpis

    def set_report_stdout(self, text):
        'Overwrite stdout text stored in report from inside a test'
        self._report_stdout = text

    def report_stdout(self):
        # If test overwrote the text, provide it:
        if self._report_stdout is not None:
            return self._report_stdout
        # Otherwise vy default provide the entire test brief log:
        if len(self.log_targets) == 2 and self.log_targets[1].log_file_path() is not None:
            with open(self.log_targets[1].log_file_path(), 'r') as myfile:
                return myfile.read()
        else:
            return 'test log file not available'

    def log_file(self):
        for lt in self.log_targets:
            if isinstance(lt, log.FileLogTarget):
                return lt
        return None

    def get_log_mark(self):
        lt = self.log_file()
        if lt is None:
            return 0
        return lt.get_mark()

    def get_log_output(self, since_mark=0):
        lt = self.log_file()
        if lt is None:
            return ''
        return lt.get_output(since_mark)

    def report_fragment(self, name, result=None, **kwargs):
        return Test.ReportFragment(parent_test=self, name=name, result=result, **kwargs)

    class ReportFragment:
        '''Add additional test results in junit XML.
           Convenient method that includes a test log:
             with test.report_fragment('foo'):
                 do_test_steps()

           Or manually add a report fragment directly:
             test.report_fragment('foo', result = test.PASS if worked else test.FAIL)
        '''

        def __init__(self, parent_test, name, result=None, output=None, since_mark=None, start_time=0.0):
            self.parent_test = parent_test
            self.name = name
            self.result = Test.UNKNOWN
            self.duration = 0.0
            self.output = output
            self.start_time = start_time
            self.log_mark = since_mark
            assert name not in (x.name for x in self.parent_test.report_fragments)
            self.parent_test.report_fragments.append(self)
            if result is not None:
                self.got_result(result)

        def __str__(self):
            return '%s/%s/%s: %s (%.1fs)' % (self.parent_test.suite_run.name(),
                    self.parent_test.name(), self.name, self.result, self.duration)

        def __enter__(self):
            self.start_time = self.parent_test.elapsed_time()
            self.log_mark = self.parent_test.get_log_mark()

        def __exit__(self, *exc_info):
            self.got_result(self.parent_test.PASS if exc_info[0] is None else self.parent_test.FAIL,
                            exc_info=exc_info)

        def got_result(self, result, exc_info=None):
            self.result = result
            self.duration = self.parent_test.elapsed_time() - self.start_time
            if self.log_mark is not None and self.output is None:
                self.output = self.parent_test.get_log_output(since_mark=self.log_mark)
            if exc_info is not None and exc_info[0] is not None:
                o = []
                if self.output:
                    o.append(self.output)
                o.extend(traceback.format_exception(*exc_info))
                self.output = '\n'.join(o)
            self.parent_test.log('----- Report fragment:', self)

# vim: expandtab tabstop=4 shiftwidth=4
