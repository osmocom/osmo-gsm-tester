# osmo_gsm_tester: read and validate config files
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
# YAML formatting is lean, but too powerful. The normal load() allows arbitrary
# code execution. There is safe_load(). But YAML also allows several
# alternative ways of formatting, better to have just one authoritative style.
# Also it would be better to receive every setting as simple string rather than
# e.g. an IMSI as an integer.
#
# The Python ConfigParserShootout page has numerous contestants, but it we want
# to use widely used, standardized parsing code without re-inventing the wheel.
# https://wiki.python.org/moin/ConfigParserShootout
#
# The optimum would be a stripped down YAML format.
# In the lack of that, we shall go with yaml.load_safe() + a round trip
# (feeding back to itself), converting keys to lowercase and values to string.

import yaml
import re
import os

from . import log

def read(path, schema=None):
    with log.Origin(path):
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        config = _standardize(config)
        if schema:
            validate(config, schema)
        return config

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


KEY_RE = re.compile('[a-zA-Z][a-zA-Z0-9_]*')

def band(val):
    if val in ('GSM-1800', 'GSM-1900'):
        return
    raise ValueError('Unknown GSM band: %r' % val)

INT = 'int'
STR = 'str'
BAND = 'band'
SCHEMA_TYPES = {
        INT: int,
        STR: str,
        BAND: band,
    }

def is_dict(l):
    return isinstance(l, dict)

def is_list(l):
    return isinstance(l, (list, tuple))

def validate(config, schema):
    '''Make sure the given config dict adheres to the schema.
       The schema is a dict of 'dict paths' in dot-notation with permitted
       value type. All leaf nodes are validated, nesting dicts are implicit.

       validate( { 'a': 123, 'b': { 'b1': 'foo', 'b2': [ 1, 2, 3 ] } },
                 { 'a': int,
                   'b.b1': str,
                   'b.b2[]': int } )

       Raise a ValueError in case the schema is violated.
    '''

    def validate_item(path, value, schema):
        want_type = schema.get(path)

        if is_list(value):
            if want_type:
                raise ValueError('config item is a list, should be %r: %r' % (want_type, path))
            path = path + '[]'
            want_type = schema.get(path)

        if not want_type:
            if is_dict(value):
                nest(path, value, schema)
                return
            if is_list(value) and value:
                for list_v in value:
                    validate_item(path, list_v, schema)
                return
            raise ValueError('config item not known: %r' % path)

        if want_type not in SCHEMA_TYPES:
            raise ValueError('unknown type %r at %r' % (want_type, path))

        if is_dict(value):
            raise ValueError('config item is dict but should be a leaf node of type %r: %r'
                             % (want_type, path))

        if is_list(value):
            for list_v in value:
                validate_item(path, list_v, schema)
            return

        with log.Origin(item=path):
            type_validator = SCHEMA_TYPES.get(want_type)
            type_validator(value)

    def nest(parent_path, config, schema):
        if parent_path:
            parent_path = parent_path + '.'
        else:
            parent_path = ''
        for k,v in config.items():
            if not KEY_RE.fullmatch(k):
                raise ValueError('invalid config key: %r' % k)
            path = parent_path + k
            validate_item(path, v, schema)

    nest(None, config, schema)

# vim: expandtab tabstop=4 shiftwidth=4
