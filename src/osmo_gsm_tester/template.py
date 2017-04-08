# osmo_gsm_tester: automated cellular network hardware tests
# Proxy to templating engine to handle files
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

import os, sys
from mako.template import Template
from mako.lookup import TemplateLookup

from . import log
from .util import dict2obj

_lookup = None
_logger = log.Origin('no templates dir set')

def set_templates_dir(*templates_dirs):
    global _lookup
    global _logger
    if not templates_dirs:
        # default templates dir is relative to this source file
        templates_dirs = [os.path.join(os.path.dirname(__file__), 'templates')]
    for d in templates_dirs:
        if not os.path.isdir(d):
            raise RuntimeError('templates dir is not a dir: %r'
                               % os.path.abspath(d))
    _lookup = TemplateLookup(directories=templates_dirs)
    _logger = log.Origin('Templates', category=log.C_CNF)

def render(name, values):
    '''feed values dict into template and return rendered result.
       ".tmpl" is added to the name to look it up in the templates dir.'''
    global _lookup
    if _lookup is None:
        set_templates_dir()
    tmpl_name = name + '.tmpl'
    with log.Origin(tmpl_name):
        template = _lookup.get_template(tmpl_name)
        _logger.dbg('rendering', tmpl_name)

        line_info_name = tmpl_name.replace('-', '_').replace('.', '_')
        return template.render(**dict2obj(values))

# vim: expandtab tabstop=4 shiftwidth=4