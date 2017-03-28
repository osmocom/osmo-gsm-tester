import sys
import time

import _prep

from osmo_gsm_tester.utils import FileLock

fl = FileLock('/tmp/lock_test', '_'.join(sys.argv[1:]))

with fl:
    print('acquired lock: %r' % fl.owner)
    sys.stdout.flush()
    time.sleep(0.5)
    print('leaving lock: %r' % fl.owner)
    sys.stdout.flush()

# vim: expandtab tabstop=4 shiftwidth=4
