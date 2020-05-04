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
import os

from . import log
from . import util

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
    if val in ('GSM-900', 'GSM-1800', 'GSM-1900'):
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
    if val not in util.ENUM_OSMO_AUTH_ALGO:
        raise ValueError('Unknown Authentication Algorithm: %r' % val)

def uint(val):
    n = int(val)
    if n < 0:
        raise ValueError('Positive value expected instead of %d' % n)

def uint8(val):
    n = int(val)
    if n < 0:
        raise ValueError('Positive value expected instead of %d' % n)
    if n > 255: # 2^8 - 1
        raise ValueError('Value %d too big, max value is 255' % n)

def uint16(val):
    n = int(val)
    if n < 0:
        raise ValueError('Positive value expected instead of %d' % n)
    if n > 65535: # 2^16 - 1
        raise ValueError('Value %d too big, max value is 65535' % n)

def times(val):
    n = int(val)
    if n < 1:
        raise ValueError('Positive value >0 expected instead of %d' % n)

def cipher(val):
    if val in ('a5_0', 'a5_1', 'a5_2', 'a5_3', 'a5_4', 'a5_5', 'a5_6', 'a5_7'):
        return
    raise ValueError('Unknown Cipher value: %r' % val)

def modem_feature(val):
    if val in ('sms', 'gprs', 'voice', 'ussd', 'sim', '2g', '3g', '4g'):
        return
    raise ValueError('Unknown Modem Feature: %r' % val)

def phy_channel_config(val):
    if val in ('CCCH', 'CCCH+SDCCH4', 'TCH/F', 'TCH/H', 'SDCCH8', 'PDCH',
               'TCH/F_PDCH', 'CCCH+SDCCH4+CBCH', 'SDCCH8+CBCH','TCH/F_TCH/H_PDCH'):
        return
    raise ValueError('Unknown Physical channel config: %r' % val)

def channel_allocator(val):
    if val in ('ascending', 'descending'):
        return
    raise ValueError('Unknown Channel Allocator Policy %r' % val)

def gprs_mode(val):
    if val in ('none', 'gprs', 'egprs'):
        return
    raise ValueError('Unknown GPRS mode %r' % val)

def codec(val):
    if val in ('hr1', 'hr2', 'hr3', 'fr1', 'fr2', 'fr3'):
        return
    raise ValueError('Unknown Codec value: %r' % val)

def osmo_trx_clock_ref(val):
    if val in ('internal', 'external', 'gspdo'):
        return
    raise ValueError('Unknown OsmoTRX clock reference value: %r' % val)

def lte_transmission_mode(val):
    n = int(val)
    if n <= 4:
        return
    raise ValueError('LTE Transmission Mode %d not in expected range' % n)

def duration(val):
    if val.isdecimal() or val.endswith('m') or val.endswith('h'):
        return
    raise ValueError('Invalid duration value: %r' % val)

INT = 'int'
STR = 'str'
UINT = 'uint'
BOOL_STR = 'bool_str'
BAND = 'band'
IPV4 = 'ipv4'
HWADDR = 'hwaddr'
IMSI = 'imsi'
KI = 'ki'
MSISDN = 'msisdn'
AUTH_ALGO = 'auth_algo'
TIMES='times'
CIPHER = 'cipher'
MODEM_FEATURE = 'modem_feature'
PHY_CHAN = 'chan'
CHAN_ALLOCATOR = 'chan_allocator'
GPRS_MODE = 'gprs_mode'
CODEC = 'codec'
OSMO_TRX_CLOCK_REF = 'osmo_trx_clock_ref'
LTE_TRANSMISSION_MODE = 'lte_transmission_mode'
DURATION = 'duration'

SCHEMA_TYPES = {
        INT: int,
        STR: str,
        UINT: uint,
        BOOL_STR: util.str2bool,
        BAND: band,
        IPV4: ipv4,
        HWADDR: hwaddr,
        IMSI: imsi,
        KI: ki,
        MSISDN: msisdn,
        AUTH_ALGO: auth_algo,
        TIMES: times,
        CIPHER: cipher,
        MODEM_FEATURE: modem_feature,
        PHY_CHAN: phy_channel_config,
        CHAN_ALLOCATOR: channel_allocator,
        GPRS_MODE: gprs_mode,
        CODEC: codec,
        OSMO_TRX_CLOCK_REF: osmo_trx_clock_ref,
        LTE_TRANSMISSION_MODE: lte_transmission_mode,
        DURATION: duration,
    }

def add(dest, src):
    if util.is_dict(dest):
        if not util.is_dict(src):
            raise ValueError('cannot add to dict a value of type: %r' % type(src))

        for key, val in src.items():
            dest_val = dest.get(key)
            if dest_val is None:
                dest[key] = val
            else:
                log.ctx(key=key)
                add(dest_val, val)
        return
    if util.is_list(dest):
        if not util.is_list(src):
            raise ValueError('cannot add to list a value of type: %r' % type(src))
        dest.extend(src)
        return
    if dest == src:
        return
    raise ValueError('cannot add dicts, conflicting items (values %r and %r)'
                     % (dest, src))

def combine(dest, src):
    if util.is_dict(dest):
        if not util.is_dict(src):
            raise ValueError('cannot combine dict with a value of type: %r' % type(src))

        for key, val in src.items():
            log.ctx(key=key)
            dest_val = dest.get(key)
            if dest_val is None:
                dest[key] = val
            else:
                combine(dest_val, val)
        return
    if util.is_list(dest):
        if not util.is_list(src):
            raise ValueError('cannot combine list with a value of type: %r' % type(src))
        # Validate that all elements in both lists are of the same type:
        t = util.list_validate_same_elem_type(src + dest)
        if t is None:
            return # both lists are empty, return
        # For lists of complex objects, we expect them to be sorted lists:
        if t in (dict, list, tuple):
            for i in range(len(dest)):
                log.ctx(idx=i)
                src_it = src[i] if i < len(src) else util.empty_instance_type(t)
                combine(dest[i], src_it)
            for i in range(len(dest), len(src)):
                log.ctx(idx=i)
                dest.append(src[i])
        else: # for lists of basic elements, we handle them as unsorted sets:
            for elem in src:
                if elem not in dest:
                    dest.append(elem)
        return
    if dest == src:
        return
    raise ValueError('cannot combine dicts, conflicting items (values %r and %r)'
                     % (dest, src))

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

        if util.is_list(value):
            if want_type:
                raise ValueError('config item is a list, should be %r: %r' % (want_type, path))
            path = path + '[]'
            want_type = schema.get(path)

        if not want_type:
            if util.is_dict(value):
                nest(path, value, schema)
                return
            if util.is_list(value) and value:
                for list_v in value:
                    validate_item(path, list_v, schema)
                return
            raise ValueError('config item not known: %r' % path)

        if want_type not in SCHEMA_TYPES:
            raise ValueError('unknown type %r at %r' % (want_type, path))

        if util.is_dict(value):
            raise ValueError('config item is dict but should be a leaf node of type %r: %r'
                             % (want_type, path))

        if util.is_list(value):
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

def generate_schemas():
    "Generate supported schemas dynamically from objects"
    obj_dir = '%s/../obj/' % os.path.dirname(os.path.abspath(__file__))
    for filename in os.listdir(obj_dir):
        if not filename.endswith(".py"):
            continue
        module_name = 'osmo_gsm_tester.obj.%s' % filename[:-3]
        util.run_python_file_method(module_name, 'on_register_schemas', False)


_RESOURCE_TYPES = ['ip_address', 'arfcn']

_RESOURCES_SCHEMA = {
        'ip_address[].addr': IPV4,
        'arfcn[].arfcn': INT,
        'arfcn[].band': BAND,
    }

_CONFIG_SCHEMA = {}

_WANT_SCHEMA = None
_ALL_SCHEMA = None

def register_resource_schema(obj_class_str, obj_attr_dict):
    """Register schema attributes for a resource type.
       For instance: register_resource_schema_attributes('modem', {'type': schema.STR, 'ki': schema.KI})
    """
    global _RESOURCES_SCHEMA
    global _RESOURCE_TYPES
    tmpdict = {}
    for key, val in obj_attr_dict.items():
        new_key = '%s[].%s' % (obj_class_str, key)
        tmpdict[new_key] = val
    combine(_RESOURCES_SCHEMA, tmpdict)
    if obj_class_str not in _RESOURCE_TYPES:
        _RESOURCE_TYPES.append(obj_class_str)

def register_config_schema(obj_class_str, obj_attr_dict):
    """Register schema attributes to configure all instances of an object class.
       For instance: register_resource_schema_attributes('bsc', {'net.codec_list[]': schema.CODEC})
    """
    global _CONFIG_SCHEMA
    tmpdict = {}
    for key, val in obj_attr_dict.items():
        new_key = '%s.%s' % (obj_class_str, key)
        tmpdict[new_key] = val
    combine(_CONFIG_SCHEMA, tmpdict)

def get_resources_schema():
    return _RESOURCES_SCHEMA;

def get_want_schema():
    global _WANT_SCHEMA
    if _WANT_SCHEMA is None:
        _WANT_SCHEMA = util.dict_add(
            dict([('%s[].times' % r, TIMES) for r in _RESOURCE_TYPES]),
            get_resources_schema())
    return _WANT_SCHEMA

def get_all_schema():
    global _ALL_SCHEMA
    if _ALL_SCHEMA is None:
        want_schema = get_want_schema()
        _ALL_SCHEMA = util.dict_add({ 'defaults.timeout': STR },
                        dict([('config.%s' % key, val) for key, val in _CONFIG_SCHEMA.items()]),
                        dict([('resources.%s' % key, val) for key, val in want_schema.items()]),
                        dict([('modifiers.%s' % key, val) for key, val in want_schema.items()]))
    return _ALL_SCHEMA

# vim: expandtab tabstop=4 shiftwidth=4
