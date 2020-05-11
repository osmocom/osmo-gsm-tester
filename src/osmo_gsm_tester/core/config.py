# osmo_gsm_tester: read and manage config files and global config
#
# Copyright (C) 2016-2020 by sysmocom - s.f.m.c. GmbH
#
# Author: Neels Hofmeyr <neels@hofmeyr.de>
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
import pprint

from . import log, util, template
from . import schema
from .util import is_dict, is_list, Dir, get_tempdir

override_conf = None

CFG_STATE_DIR = 'state_dir'
CFG_SUITES_DIR = 'suites_dir'
CFG_SCENARIOS_DIR = 'scenarios_dir'
CFG_DEFAULT_SUITES_CONF = 'default_suites_conf_path'
CFG_DEFAULTS_CONF = 'defaults_conf_path'
CFG_RESOURCES_CONF = 'resource_conf_path'
MAIN_CONFIG_SCHEMA = {
        CFG_STATE_DIR: schema.STR,
        CFG_SUITES_DIR: schema.STR,
        CFG_SCENARIOS_DIR: schema.STR,
        CFG_DEFAULT_SUITES_CONF: schema.STR,
        CFG_DEFAULTS_CONF: schema.STR,
        CFG_RESOURCES_CONF: schema.STR,
    }

DF_CFG_STATE_DIR = '/var/tmp/osmo-gsm-tester/state/'
DF_CFG_SUITES_DIR = './suites'
DF_CFG_SCENARIOS_DIR = './scenarios'
DF_CFG_DEFAULT_SUITES_CONF = './default-suites.conf'
DF_CFG_DEFAULTS_CONF = './defaults.conf'
DF_CFG_RESOURCES_CONF = './resources.conf'

DEFAULT_CONFIG_FILENAME = 'main.conf'

DEFAULT_CONFIG_LOCATIONS = [
    '.',
    os.path.join(os.getenv('HOME'), '.config', 'osmo-gsm-tester', DEFAULT_CONFIG_FILENAME),
    os.path.join('/usr/local/etc/osmo-gsm-tester', DEFAULT_CONFIG_FILENAME),
    os.path.join('/etc/osmo-gsm-tester', DEFAULT_CONFIG_FILENAME)
    ]

MAIN_CONFIG = None
MAIN_CONFIG_PATH = None

def _find_main_config_path():
    if override_conf:
        locations = [ override_conf ]
    elif os.getenv('OSMO_GSM_TESTER_CONF'):
        ENV_CONF = os.getenv('OSMO_GSM_TESTER_CONF')
        log.err('Using environment variable OSMO_GSM_TESTER_CONF=%s(/paths.conf) is deprecated. Rather use -c command line argument!' % ENV_CONF)
        locations = [ ENV_CONF + 'paths.conf' ] # directory is expected in OSMO_GSM_TESTER_CONF, bakcward compatibility
    else:
        locations = DEFAULT_CONFIG_LOCATIONS

    for l in locations:
        real_l = os.path.realpath(l)
        if os.path.isfile(real_l):
            log.dbg('Found main configuration file in ', l, 'which is', real_l, _category=log.C_CNF)
            return real_l
    raise RuntimeError('Main configuration file not found in %r' % ([l for l in locations]))

def _get_main_config_path():
    global MAIN_CONFIG_PATH
    if MAIN_CONFIG_PATH is None:
        MAIN_CONFIG_PATH = _find_main_config_path()
    return MAIN_CONFIG_PATH

def main_config_path_to_abspath(path):
    'Relative files in main config are relative towards the config file, not towards $CWD'
    if not path.startswith(os.pathsep):
        return os.path.realpath(os.path.join(os.path.dirname(_get_main_config_path()), path))
    return path

def _get_main_config():
    global MAIN_CONFIG
    if MAIN_CONFIG is None:
        cfg = read(_get_main_config_path(), MAIN_CONFIG_SCHEMA)
        MAIN_CONFIG = {
            CFG_STATE_DIR: DF_CFG_STATE_DIR,
            CFG_SUITES_DIR: DF_CFG_SUITES_DIR,
            CFG_SCENARIOS_DIR: DF_CFG_SCENARIOS_DIR,
            CFG_DEFAULT_SUITES_CONF: DF_CFG_DEFAULT_SUITES_CONF,
            CFG_DEFAULTS_CONF: DF_CFG_DEFAULTS_CONF,
            CFG_RESOURCES_CONF: DF_CFG_RESOURCES_CONF,
            }
        overlay(MAIN_CONFIG, cfg)
        for key, path in sorted(MAIN_CONFIG.items()):
             MAIN_CONFIG[key] = main_config_path_to_abspath(path)
        log.dbg('MAIN CONFIG:\n' + pprint.pformat(MAIN_CONFIG), _category=log.C_CNF)
    return MAIN_CONFIG

def get_main_config_value(cfg_name, fail_if_missing=True):
    cfg = _get_main_config()
    f = cfg.get(cfg_name, None)
    if f is None and fail_if_missing:
        raise RuntimeError('Missing configuration %s' % (cfg_name))
    return f

def read_config_file(cfg_name, validation_schema=None, if_missing_return=False):
    '''Read content of config file cfg_name (referring to key in main config).
    If "if_missing_return" is different than False, then instead of failing it will return whatever it is stored in that arg
    '''
    fail_if_missing = True
    if if_missing_return is not False:
        fail_if_missing = False
    path = get_main_config_value(cfg_name, fail_if_missing=fail_if_missing)
    if path is None:
        return if_missing_return
    return read(path, validation_schema=validation_schema, if_missing_return=if_missing_return)

def get_state_dir():
    return Dir(get_main_config_value(CFG_STATE_DIR))

def get_suites_dir():
    return Dir(get_main_config_value(CFG_SUITES_DIR))

def get_scenarios_dir():
    return Dir(get_main_config_value(CFG_SCENARIOS_DIR))

DEFAULTS_CONF = None
def get_defaults(for_kind):
    global DEFAULTS_CONF
    if DEFAULTS_CONF is None:
        DEFAULTS_CONF = read_config_file(CFG_DEFAULTS_CONF, if_missing_return={})
    defaults = DEFAULTS_CONF.get(for_kind, {})
    return copy.deepcopy(defaults)

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

def fromstr(config_str, validation_schema=None):
    config = yaml.safe_load(config_str)
    config = _standardize(config)
    if validation_schema is not None:
        schema.validate(config, validation_schema)
    return config

def tostr(config):
    return _tostr(_standardize(config))

def _tostr(config):
    return yaml.dump(config, default_flow_style=False)

def _standardize_item(item):
    if item is None:
        return None
    if isinstance(item, (tuple, list)):
        return [_standardize_item(i) for i in item]
    if isinstance(item, dict):
        return dict([(key.lower(), _standardize_item(val)) for key,val in item.items()])
    return str(item)

def _standardize(config):
    config = yaml.safe_load(_tostr(_standardize_item(config)))
    return config

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
        copy_len = min(len(src),len(dest))
        for i in range(copy_len):
            log.ctx(idx=i)
            dest[i] = overlay(dest[i], src[i])
        for i in range(copy_len, len(src)):
            dest.append(src[i])
        return dest
    return src

def replicate_times(d):
    '''
    replicate items that have a "times" > 1

    'd' is a dict matching WANT_SCHEMA, which is the same as
    the RESOURCES_SCHEMA, except each entity that can be reserved has a 'times'
    field added, to indicate how many of those should be reserved.
    '''
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
