# osmo_gsm_tester: Suite scenario
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

import os

from . import log
from . import template
from . import config

class Scenario(log.Origin, dict):
    def __init__(self, name, path, param_list=[]):
        super().__init__(log.C_TST, name)
        self.path = path
        self.param_list = param_list

    @classmethod
    def count_cont_char_backward(cls, str, before_pos, c):
        n = 0
        i = before_pos - 1
        while i >= 0:
            if str[i] != c:
                break
            n += 1
            i -= 1
        return n

    @classmethod
    def split_scenario_parameters(cls, str):
        cur_pos = 0
        param_li = []
        saved = ''
        # Split into a list, but we want to escape '\,' to avoid splitting parameters containing commas.
        while True:
            prev_pos = cur_pos
            cur_pos = str.find(',', prev_pos)
            if cur_pos == -1:
                param_li.append(str[prev_pos:])
                break
            if cur_pos == 0:
                param_li.append('')
            elif cur_pos != 0 and str[cur_pos - 1] == '\\' and cls.count_cont_char_backward(str, cur_pos, '\\') % 2 == 1:
                saved += str[prev_pos:cur_pos - 1] + ','
            else:
                param_li.append(saved + str[prev_pos:cur_pos])
                saved = ''
            cur_pos += 1
        i = 0
        # Also escape '\\' -> '\'
        while i < len(param_li):
            param_li[i] = param_li[i].replace('\\\\', '\\')
            i += 1
        return param_li

    @classmethod
    def from_param_list_str(cls, name, path, param_list_str):
        param_list = cls.split_scenario_parameters(param_list_str)
        return cls(name, path, param_list)

    def read_from_file(self, validation_schema):
        with open(self.path, 'r') as f:
            config_str = f.read()
        if len(self.param_list) != 0:
            param_dict = {}
            i = 1
            for param in self.param_list:
                param_dict['param' + str(i)] = param
                i += 1
            self.dbg(param_dict=param_dict)
            config_str = template.render_strbuf_inline(config_str, param_dict)
        conf = config.fromstr(config_str, validation_schema)
        self.update(conf)

def get_scenario(name, validation_schema=None):
    scenarios_dir = config.get_scenarios_dir()
    if not name.endswith('.conf'):
        name = name + '.conf'
    is_parametrized_file = '@' in name
    param_list = []
    path = scenarios_dir.child(name)
    if not is_parametrized_file:
        if not os.path.isfile(path):
            raise RuntimeError('No such scenario file: %r' % path)
        sc = Scenario(name, path)
    else: # parametrized scenario:
        # Allow first matching complete matching names (eg: scenario@param1,param2.conf),
        # this allows setting specific content in different files for specific values.
        if not os.path.isfile(path):
            # get "scenario@.conf" from "scenario@param1,param2.conf":
            prefix_name = name[:name.index("@")+1] + '.conf'
            path = scenarios_dir.child(prefix_name)
            if not os.path.isfile(path):
                raise RuntimeError('No such scenario file: %r (nor %s)' % (path, name))
        # At this point, we have existing file path. Let's now scrap the parameter(s):
        # get param1,param2 str from scenario@param1,param2.conf
        param_list_str = name.split('@', 1)[1][:-len('.conf')]
        sc = Scenario.from_param_list_str(name, path, param_list_str)
    sc.read_from_file(validation_schema)
    return sc

# vim: expandtab tabstop=4 shiftwidth=4
