# osmo_gsm_tester: validate dict structures
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

import re

from . import log
from .util import is_dict, is_list, str2bool

KEY_RE = re.compile('[a-zA-Z][a-zA-Z0-9_]*')
IPV4_RE = re.compile('([0-9]{1,3}.){3}[0-9]{1,3}')
HWADDR_RE = re.compile('([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}')
IMSI_RE = re.compile('[0-9]{6,15}')
KI_RE = re.compile('[0-9a-fA-F]{32}')
MSISDN_RE = re.compile('[0-9]{1,15}')

def match_re(name, regex, val):
    while True:
        if not isinstance(val, str):
            break;
        if not regex.fullmatch(val):
            break;
        return
    raise ValueError('Invalid %s: %r' % (name, val))

def band(val):
    if val in ('GSM-1800', 'GSM-1900'):
        return
    raise ValueError('Unknown GSM band: %r' % val)

def ipv4(val):
    match_re('IPv4 address', IPV4_RE, val)
    els = [int(el) for el in val.split('.')]
    if not all([el >= 0 and el <= 255 for el in els]):
        raise ValueError('Invalid IPv4 address: %r' % val)

def hwaddr(val):
    match_re('hardware address', HWADDR_RE, val)

def imsi(val):
    match_re('IMSI', IMSI_RE, val)

def ki(val):
    match_re('KI', KI_RE, val)

def msisdn(val):
    match_re('MSISDN', MSISDN_RE, val)

def auth_algo(val):
    if val in ('none', 'xor', 'comp128v1'):
        return
    raise ValueError('Unknown Authentication Algorithm: %r' % val)

INT = 'int'
STR = 'str'
BOOL_STR = 'bool_str'
BAND = 'band'
IPV4 = 'ipv4'
HWADDR = 'hwaddr'
IMSI = 'imsi'
KI = 'ki'
MSISDN = 'msisdn'
AUTH_ALGO = 'auth_algo'
SCHEMA_TYPES = {
        INT: int,
        STR: str,
        BOOL_STR: str2bool,
        BAND: band,
        IPV4: ipv4,
        HWADDR: hwaddr,
        IMSI: imsi,
        KI: ki,
        MSISDN: msisdn,
        AUTH_ALGO: auth_algo,
    }

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

        log.ctx(path)
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
