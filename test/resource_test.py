#!/usr/bin/env python3

import tempfile
import os

import _prep

from osmo_gsm_tester import config, log, resource


workdir = tempfile.mkdtemp()
try:

    r = resource.Resources(os.path.join(_prep.script_dir, 'etc', 'resources.conf'),
                           workdir)

finally:
	os.removedirs(workdir)

# vim: expandtab tabstop=4 shiftwidth=4
