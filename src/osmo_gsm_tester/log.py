# osmo_gsm_tester: global logging
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
import sys
import time
import traceback
import contextlib
from inspect import getframeinfo, stack

L_ERR = 30
L_LOG = 20
L_DBG = 10
L_TRACEBACK = 'TRACEBACK'

LEVEL_STRS = {
            'err': L_ERR,
            'log': L_LOG,
            'dbg': L_DBG,
        }

C_NET = 'net'
C_RUN = 'run'
C_TST = 'tst'
C_CNF = 'cnf'
C_BUS = 'bus'
C_DEFAULT = '---'

LONG_DATEFMT = '%Y-%m-%d_%H:%M:%S'
DATEFMT = '%H:%M:%S'

# may be overridden by regression tests
get_process_id = lambda: '%d-%d' % (os.getpid(), time.time())

class Error(Exception):
    pass

class LogTarget:
    do_log_time = None
    do_log_category = None
    do_log_level = None
    do_log_origin = None
    do_log_traceback = None
    do_log_src = None
    origin_width = None
    origin_fmt = None
    all_levels = None

    # redirected by logging test
    get_time_str = lambda self: time.strftime(self.log_time_fmt)

    # sink that gets each complete logging line
    log_sink = sys.__stdout__.write

    category_levels = None

    def __init__(self):
        self.category_levels = {}
        self.style()

    def style(self, time=True, time_fmt=DATEFMT, category=True, level=True, origin=True, origin_width=0, src=True, trace=False):
        '''
        set all logging format aspects, to defaults if not passed:
        time: log timestamps;
        time_fmt: format of timestamps;
        category: print the logging category (three letters);
        level: print the logging level, unless it is L_LOG;
        origin: print which object(s) the message originated from;
        origin_width: fill up the origin string with whitespace to this witdh;
        src: log the source file and line number the log comes from;
        trace: on exceptions, log the full stack trace;
        '''
        self.log_time_fmt = time_fmt
        self.do_log_time = bool(time)
        if not self.log_time_fmt:
            self.do_log_time = False
        self.do_log_category = bool(category)
        self.do_log_level = bool(level)
        self.do_log_origin = bool(origin)
        self.origin_width = int(origin_width)
        self.origin_fmt = '{:>%ds}' % self.origin_width
        self.do_log_src = src
        self.do_log_traceback = trace

    def style_change(self, time=None, time_fmt=None, category=None, level=None, origin=None, origin_width=None, src=None, trace=None):
        'modify only the given aspects of the logging format'
        self.style(
            time=(time if time is not None else self.do_log_time),
            time_fmt=(time_fmt if time_fmt is not None else self.log_time_fmt),
            category=(category if category is not None else self.do_log_category),
            level=(level if level is not None else self.do_log_level),
            origin=(origin if origin is not None else self.do_log_origin),
            origin_width=(origin_width if origin_width is not None else self.origin_width),
            src=(src if src is not None else self.do_log_src),
            trace=(trace if trace is not None else self.do_log_traceback),
            )

    def set_level(self, category, level):
        'set global logging log.L_* level for a given log.C_* category'
        self.category_levels[category] = level

    def set_all_levels(self, level):
        self.all_levels = level

    def is_enabled(self, category, level):
        if level == L_TRACEBACK:
            return self.do_log_traceback
        if self.all_levels is not None:
            is_level = self.all_levels
        else:
            is_level = self.category_levels.get(category)
        if is_level is None:
            is_level = L_LOG
        if level < is_level:
            return False
        return True

    def log(self, origin, category, level, src, messages, named_items):
        if category and len(category) != 3:
            self.log_sink('WARNING: INVALID LOG SUBSYSTEM %r\n' % category)
            self.log_sink('origin=%r category=%r level=%r\n' % (origin, category, level));

        if not category:
            category = C_DEFAULT
        if not self.is_enabled(category, level):
            return

        log_pre = []
        if self.do_log_time:
            log_pre.append(self.get_time_str())

        if self.do_log_category:
            log_pre.append(category)

        deeper_origins = ''
        if self.do_log_origin:
            if origin is None:
                name = '-'
            elif isinstance(origin, Origins):
                name = origin[-1]
                if len(origin) > 1:
                    deeper_origins = str(origin)
            elif isinstance(origin, str):
                name = origin or None
            elif hasattr(origin, 'name'):
                name = origin.name()
            if not name:
                name = str(origin.__class__.__name__)
            log_pre.append(self.origin_fmt.format(name))

        if self.do_log_level and level != L_LOG:
            loglevel = '%s: ' % (level_str(level) or ('loglevel=' + str(level)))
        else:
            loglevel = ''

        log_line = [compose_message(messages, named_items)]

        if deeper_origins:
            log_line.append(' [%s]' % deeper_origins)

        if self.do_log_src and src:
            log_line.append(' [%s]' % str(src))

        log_str = '%s%s%s%s' % (' '.join(log_pre),
                              ': ' if log_pre else '',
                              loglevel,
                              ' '.join(log_line))

        if not log_str.endswith('\n'):
            log_str = log_str + '\n'
        self.log_sink(log_str)

targets = [ LogTarget() ]

def level_str(level):
    if level == L_TRACEBACK:
        return L_TRACEBACK
    if level <= L_DBG:
        return 'DBG'
    if level <= L_LOG:
        return 'LOG'
    return 'ERR'

def _log_all_targets(origin, category, level, src, messages, named_items=None):
    global targets

    if origin is None:
        origin = Origin._global_current_origin
    if isinstance(src, int):
        src = get_src_from_caller(src + 1)
    for target in targets:
        target.log(origin, category, level, src, messages, named_items)

def get_src_from_caller(levels_up=1):
    caller = getframeinfo(stack()[levels_up][0])
    return '%s:%d' % (os.path.basename(caller.filename), caller.lineno)

def get_src_from_tb(tb, levels_up=1):
    ftb = traceback.extract_tb(tb)
    f,l,m,c = ftb[-levels_up]
    f = os.path.basename(f)
    return '%s:%s: %s' % (f, l, c)

def get_line_for_src(src_path):
    etype, exception, tb = sys.exc_info()
    if tb:
        ftb = traceback.extract_tb(tb)
        for f,l,m,c in ftb:
            if f.endswith(src_path):
                return l

    for frame in stack():
        caller = getframeinfo(frame[0])
        if caller.filename.endswith(src_path):
            return caller.lineno
    return None


class Origin:
    '''
    Base class for all classes that want to log,
    and to add an origin string to a code path:
    with log.Origin('my name'):
        raise Problem()
    This will log 'my name' as an origin for the Problem.
    '''

    _global_current_origin = None
    _global_id = None

    _log_category = None
    _src = None
    _name = None
    _origin_id = None

    _parent_origin = None

    def __init__(self, *name_items, category=None, **detail_items):
        self.set_log_category(category)
        self.set_name(*name_items, **detail_items)

    def set_name(self, *name_items, **detail_items):
        if name_items:
            name = '-'.join([str(i) for i in name_items])
        elif not detail_items:
            name = self.__class__.__name__
        else:
            name = ''
        if detail_items:
            details = '(%s)' % (', '.join([("%s=%r" % (k,v))
                                           for k,v in sorted(detail_items.items())]))
        else:
            details = ''
        self._name = name + details

    def name(self):
        return self._name or self.__class__.__name__

    __str__ = name
    __repr__ = name

    def origin_id(self):
        if not self._origin_id:
            if not Origin._global_id:
                Origin._global_id = get_process_id()
            self._origin_id = '%s-%s' % (self.name(), Origin._global_id)
        return self._origin_id

    def set_log_category(self, category):
        self._log_category = category

    def _log(self, level, messages, named_items=None, src_levels_up=3, origins=None):
        src = self._src or src_levels_up
        origin = origins or self.gather_origins()
        _log_all_targets(origin, self._log_category, level, src, messages, named_items)

    def dbg(self, *messages, **named_items):
        self._log(L_DBG, messages, named_items)

    def log(self, *messages, **named_items):
        self._log(L_LOG, messages, named_items)

    def err(self, *messages, **named_items):
        self._log(L_ERR, messages, named_items)

    def log_exn(self, exc_info=None):
        log_exn(self, self._log_category, exc_info)

    def __enter__(self):
        if not self.set_child_of(Origin._global_current_origin):
            return
        Origin._global_current_origin = self

    def __exit__(self, *exc_info):
        rc = None
        if exc_info[0] is not None:
            rc = exn_add_info(exc_info, self)
        Origin._global_current_origin, self._parent_origin = self._parent_origin, None
        return rc

    def raise_exn(self, *messages, exn_class=Error, **named_items):
        with self:
            raise exn_class(compose_message(messages, named_items))

    def redirect_stdout(self):
        return contextlib.redirect_stdout(SafeRedirectStdout(self))

    def gather_origins(self):
        origins = Origins()
        origins.add(self)
        origin = self._parent_origin
        if origin is None and Origin._global_current_origin is not None:
            origin = Origin._global_current_origin
        while origin is not None:
            origins.add(origin)
            origin = origin._parent_origin
        return origins

    def set_child_of(self, parent_origin):
        # avoid loops
        if self._parent_origin is not None:
            return False
        if parent_origin == self:
            return False
        self._parent_origin = parent_origin
        return True

class LineInfo(Origin):
    def __init__(self, src_file, *name_items, **detail_items):
        self.src_file = src_file
        self.set_name(*name_items, **detail_items)

    def name(self):
        l = get_line_for_src(self.src_file)
        if l is not None:
            return '%s:%s' % (self._name, l)
        return super().name()

class SafeRedirectStdout:
    '''
    To be able to use 'print' in test scripts, this is used to redirect stdout
    to a test class' log() function. However, it turns out doing that breaks
    python debugger sessions -- it uses extended features of stdout, and will
    fail dismally if it finds this wrapper in sys.stdout. Luckily, overriding
    __getattr__() to return the original sys.__stdout__ attributes for anything
    else than write() makes the debugger session work nicely again!
    '''
    _log_line_buf = None

    def __init__(self, origin):
        self._origin = origin

    def write(self, message):
        lines = message.splitlines()
        if not lines:
            return
        if self._log_line_buf:
            lines[0] = self._log_line_buf + lines[0]
            self._log_line_buf = None
        if not message.endswith('\n'):
            self._log_line_buf = lines[-1]
            lines = lines[:-1]
        origins = self._origin.gather_origins()
        for line in lines:
            self._origin._log(L_LOG, (line,), origins=origins)

    def __getattr__(self, name):
        return sys.__stdout__.__getattribute__(name)


def dbg(origin, category, *messages, **named_items):
    _log_all_targets(origin, category, L_DBG, 2, messages, named_items)

def log(origin, category, *messages, **named_items):
    _log_all_targets(origin, category, L_LOG, 2, messages, named_items)

def err(origin, category, *messages, **named_items):
    _log_all_targets(origin, category, L_ERR, 2, messages, named_items)

def trace(origin, category, exc_info):
    _log_all_targets(origin, category, L_TRACEBACK, None,
                     traceback.format_exception(*exc_info))

def resolve_category(origin, category):
    if category is not None:
        return category
    if not hasattr(origin, '_log_category'):
        return None
    return origin._log_category

def exn_add_info(exc_info, origin, category=None):
    etype, exception, tb = exc_info
    if not hasattr(exception, 'origins'):
        exception.origins = Origins()
    if not hasattr(exception, 'category'):
        # only remember the deepest category
        exception.category = resolve_category(origin, category)
    if not hasattr(exception, 'src'):
        exception.src = get_src_from_tb(tb)
    exception.origins.add(origin)
    return False



def log_exn(origin=None, category=None, exc_info=None):
    if not (exc_info is not None and len(exc_info) == 3):
        exc_info = sys.exc_info()
        if not (exc_info is not None and len(exc_info) == 3):
            raise RuntimeError('invalid call to log_exn() -- no valid exception info')

    etype, exception, tb = exc_info

    # if there are origins recorded with the Exception, prefer that
    if hasattr(exception, 'origins'):
        origin = exception.origins

    # if there is a category recorded with the Exception, prefer that
    if hasattr(exception, 'category'):
        category = exception.category

    if hasattr(exception, 'msg'):
        msg = exception.msg
    else:
        msg = str(exception)

    if hasattr(exception, 'src'):
        src = exception.src
    else:
        src = 2

    trace(origin, category, exc_info)
    _log_all_targets(origin, category, L_ERR, src,
                     ('%s:' % str(etype.__name__), msg))


class Origins(list):
    def __init__(self, origin=None):
        if origin is not None:
            self.add(origin)
    def add(self, origin):
        if hasattr(origin, 'name'):
            origin_str = origin.name()
        else:
            origin_str = repr(origin)
        if origin_str is None:
            raise RuntimeError('origin_str is None for %r' % origin)
        self.insert(0, origin_str)
    def __str__(self):
        return '↪'.join(self)



def set_all_levels(level):
    global targets
    for target in targets:
        target.set_all_levels(level)

def set_level(category, level):
    global targets
    for target in targets:
        target.set_level(category, level)

def style(**kwargs):
    global targets
    for target in targets:
        target.style(**kwargs)

def style_change(**kwargs):
    global targets
    for target in targets:
        target.style_change(**kwargs)

class TestsTarget(LogTarget):
    'LogTarget producing deterministic results for regression tests'
    def __init__(self, out=sys.stdout):
        super().__init__()
        self.style(time=False, src=False)
        self.log_sink = out.write

def run_logging_exceptions(func, *func_args, return_on_failure=None, **func_kwargs):
    try:
        return func(*func_args, **func_kwargs)
    except:
        log_exn()
        return return_on_failure

def compose_message(messages, named_items):
    msgs = [str(m) for m in messages]

    if named_items:
        # unfortunately needs to be sorted to get deterministic results
        msgs.append('{%s}' %
                    (', '.join(['%s=%r' % (k,v)
                     for k,v in sorted(named_items.items())])))

    return ' '.join(msgs)

# vim: expandtab tabstop=4 shiftwidth=4
