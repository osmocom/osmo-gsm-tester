# osmo_gsm_tester: read and manage config files and global config
#
# Copyright (C) 2016-2017 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
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

# discussion for choice of config file format:
#
# Python syntax is insane, because it allows the config file to run arbitrary
# python commands.
#
# INI file format is nice and simple, but it doesn't allow having the same
# section numerous times (e.g. to define several modems or BTS models) and does
# not support nesting.
#
# JSON has too much braces and quotes to be easy to type
#
# YAML formatting is lean, but:
# - too powerful. The normal load() allows arbitrary code execution. There is
#   safe_load().
# - allows several alternative ways of formatting, better to have just one
#   authoritative style.
# - tries to detect types. It would be better to receive every setting as
#   simple string rather than e.g. an IMSI as an integer.
# - e.g. an IMSI starting with a zero is interpreted as octal value, resulting
#   in super confusing error messages if the user merely forgets to quote it.
# - does not tell me which line a config item came from, so no detailed error
#   message is possible.
#
# The Python ConfigParserShootout page has numerous contestants, but many of
# those seem to be not widely used / standardized or even tested.
# https://wiki.python.org/moin/ConfigParserShootout
#
# The optimum would be a stripped down YAML format.
# In the lack of that, we shall go with yaml.load_safe() + a round trip
# (feeding back to itself), converting keys to lowercase and values to string.
# There is no solution for octal interpretations nor config file source lines
# unless, apparently, we implement our own config parser.

import yaml
import os
import copy

from . import log, schema, util
from .util import is_dict, is_list, Dir, get_tempdir

ENV_PREFIX = 'OSMO_GSM_TESTER_'
ENV_CONF = os.getenv(ENV_PREFIX + 'CONF')

override_conf = None

DEFAULT_CONFIG_LOCATIONS = [
    '.',
    os.path.join(os.getenv('HOME'), '.config', 'osmo-gsm-tester'),
    '/usr/local/etc/osmo-gsm-tester',
    '/etc/osmo-gsm-tester'
    ]

PATHS_CONF = 'paths.conf'
DEFAULT_SUITES_CONF = 'default-suites.conf'
PATH_STATE_DIR = 'state_dir'
PATH_SUITES_DIR = 'suites_dir'
PATH_SCENARIOS_DIR = 'scenarios_dir'
PATHS_SCHEMA = {
        PATH_STATE_DIR: schema.STR,
        PATH_SUITES_DIR: schema.STR,
        PATH_SCENARIOS_DIR: schema.STR,
    }

PATHS_TEMPDIR_STR = '$TEMPDIR'

PATHS = None

def _get_config_file(basename, fail_if_missing=True):
    if override_conf:
        locations = [ override_conf ]
    elif ENV_CONF:
        locations = [ ENV_CONF ]
    else:
        locations = DEFAULT_CONFIG_LOCATIONS

    for l in locations:
        real_l = os.path.realpath(l)
        p = os.path.realpath(os.path.join(real_l, basename))
        if os.path.isfile(p):
            log.dbg('Found config file', basename, 'as', p, 'in', l, 'which is', real_l, _category=log.C_CNF)
            return (p, real_l)
    if not fail_if_missing:
        return None, None
    raise RuntimeError('configuration file not found: %r in %r' % (basename,
        [os.path.abspath(p) for p in locations]))

def get_config_file(basename, fail_if_missing=True):
    path, found_in = _get_config_file(basename, fail_if_missing)
    return path

def read_config_file(basename, validation_schema=None, if_missing_return=False):
    fail_if_missing = True
    if if_missing_return is not False:
        fail_if_missing = False
    path = get_config_file(basename, fail_if_missing=fail_if_missing)
    if path is None:
        return if_missing_return
    return read(path, validation_schema=validation_schema, if_missing_return=if_missing_return)

def get_configured_path(label, allow_unset=False):
    global PATHS

    env_name = ENV_PREFIX + label.upper()
    env_path = os.getenv(env_name)
    if env_path:
        real_env_path = os.path.realpath(env_path)
        log.dbg('Found path', label, 'as', env_path, 'in', '$' + env_name, 'which is', real_env_path, _category=log.C_CNF)
        return real_env_path

    if PATHS is None:
        paths_file, found_in = _get_config_file(PATHS_CONF)
        PATHS = read(paths_file, PATHS_SCHEMA)
        # sorted for deterministic regression test results
        for key, path in sorted(PATHS.items()):
            if not path.startswith(os.pathsep):
                PATHS[key] = os.path.realpath(os.path.join(found_in, path))
                log.dbg(paths_file + ': relative path', path, 'is', PATHS[key], _category=log.C_CNF)
    p = PATHS.get(label)
    if p is None and not allow_unset:
        raise RuntimeError('missing configuration in %s: %r' % (PATHS_CONF, label))

    log.dbg('Found path', label, 'as', p, _category=log.C_CNF)
    if p.startswith(PATHS_TEMPDIR_STR):
        p = os.path.join(get_tempdir(), p[len(PATHS_TEMPDIR_STR):])
        log.dbg('Path', label, 'contained', PATHS_TEMPDIR_STR, 'and becomes', p, _category=log.C_CNF)
    return p

def get_state_dir():
    return Dir(get_configured_path(PATH_STATE_DIR))

def get_suites_dir():
    return Dir(get_configured_path(PATH_SUITES_DIR))

def get_scenarios_dir():
    return Dir(get_configured_path(PATH_SCENARIOS_DIR))

def read(path, validation_schema=None, if_missing_return=False):
    log.ctx(path)
    if not os.path.isfile(path) and if_missing_return is not False:
        return if_missing_return
    with open(path, 'r') as f:
        config = yaml.safe_load(f)
    config = _standardize(config)
    if validation_schema:
        schema.validate(config, validation_schema)
    return config

def write(path, config):
    log.ctx(path)
    with open(path, 'w') as f:
        f.write(tostr(config))

def tostr(config):
    return _tostr(_standardize(config))

def _tostr(config):
    return yaml.dump(config, default_flow_style=False)

def _standardize_item(item):
    if isinstance(item, (tuple, list)):
        return [_standardize_item(i) for i in item]
    if isinstance(item, dict):
        return dict([(key.lower(), _standardize_item(val)) for key,val in item.items()])
    return str(item)

def _standardize(config):
    config = yaml.safe_load(_tostr(_standardize_item(config)))
    return config

def get_defaults(for_kind):
    defaults = read_config_file('defaults.conf', if_missing_return={})
    return defaults.get(for_kind, {})

class Scenario(log.Origin, dict):
    def __init__(self, name, path):
        super().__init__(log.C_TST, name)
        self.path = path

def get_scenario(name, validation_schema=None):
    scenarios_dir = get_scenarios_dir()
    if not name.endswith('.conf'):
        name = name + '.conf'
    path = scenarios_dir.child(name)
    if not os.path.isfile(path):
        raise RuntimeError('No such scenario file: %r' % path)
    sc = Scenario(name, path)
    sc.update(read(path, validation_schema=validation_schema))
    return sc

def add(dest, src):
    if is_dict(dest):
        if not is_dict(src):
            raise ValueError('cannot add to dict a value of type: %r' % type(src))

        for key, val in src.items():
            dest_val = dest.get(key)
            if dest_val is None:
                dest[key] = val
            else:
                log.ctx(key=key)
                add(dest_val, val)
        return
    if is_list(dest):
        if not is_list(src):
            raise ValueError('cannot add to list a value of type: %r' % type(src))
        dest.extend(src)
        return
    if dest == src:
        return
    raise ValueError('cannot add dicts, conflicting items (values %r and %r)'
                     % (dest, src))

def combine(dest, src):
    if is_dict(dest):
        if not is_dict(src):
            raise ValueError('cannot combine dict with a value of type: %r' % type(src))

        for key, val in src.items():
            log.ctx(key=key)
            dest_val = dest.get(key)
            if dest_val is None:
                dest[key] = val
            else:
                combine(dest_val, val)
        return
    if is_list(dest):
        if not is_list(src):
            raise ValueError('cannot combine list with a value of type: %r' % type(src))
        for i in range(len(src)):
            log.ctx(idx=i)
            combine(dest[i], src[i])
        return
    if dest == src:
        return
    raise ValueError('cannot combine dicts, conflicting items (values %r and %r)'
                     % (dest, src))

def overlay(dest, src):
    if is_dict(dest):
        if not is_dict(src):
            raise ValueError('cannot combine dict with a value of type: %r' % type(src))

        for key, val in src.items():
            log.ctx(key=key)
            dest_val = dest.get(key)
            dest[key] = overlay(dest_val, val)
        return dest
    if is_list(dest):
        if not is_list(src):
            raise ValueError('cannot combine list with a value of type: %r' % type(src))
        for i in range(len(src)):
            log.ctx(idx=i)
            dest[i] = overlay(dest[i], src[i])
        return dest
    return src

def replicate_times(d):
    'replicate items that have a "times" > 1'
    d = copy.deepcopy(d)
    for key, item_list in d.items():
        idx = 0
        while idx < len(item_list):
            item = item_list[idx]
            times = int(item.pop('times', 1))
            for j in range(1, times):
                item_list.insert(idx + j, copy.deepcopy(item))
            idx += times
    return d

# vim: expandtab tabstop=4 shiftwidth=4
