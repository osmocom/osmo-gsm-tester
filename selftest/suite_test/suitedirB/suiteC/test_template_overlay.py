#!/usr/bin/env python3
from osmo_gsm_tester.testenv import *

import os
import sys

print('- Testing: expect to fail on invalid templates overlay dir')
try:
    #stp.configure()
    tenv.set_overlay_template_dir(os.path.join(os.path.dirname(__file__), 'nonexistent-templatedir'))
    sys.stderr.write('Error: setting non-existing templates dir should raise RuntimeError\n')
    assert(False)
except RuntimeError:
    print('success: setting non-existing templates dir raised RuntimeError')
    pass

mytemplatedir = os.path.join(os.path.dirname(__file__), 'mytemplatedir')
tenv.set_overlay_template_dir(mytemplatedir)

stp = tenv.stp()
print('- Testing: original template')
stp.configure()

print('- Testing:overlay template')
mytemplatefile = os.path.join(mytemplatedir, 'osmo-stp.cfg.tmpl')
try:
    with open(mytemplatefile, 'w') as f:
        r = """! Overlay Config file genreated by test
line vty
 no login
 bind ${stp.ip_address.addr}
        """
        f.write(r)

    # After creating the new template, it won\'t be used until
    # set_overlay_template_dir() is called again because the templates are
    # somehow cached by mako.
    print('- After creating the new template, still old template is used' )
    stp.configure()
    print('- New template is used after re-generating cache with set_overlay_template_dir:')
    tenv.set_overlay_template_dir(mytemplatedir)
    stp.configure()
finally:
    os.remove(mytemplatefile)
