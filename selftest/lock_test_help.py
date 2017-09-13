import sys
import time
import os

import _prep

from osmo_gsm_tester.util import FileLock, touch_file

testdir, name = sys.argv[1:]
stop_signalling_file = os.path.join(testdir, name)
if not os.path.isfile(stop_signalling_file):
    print('expected a stop-file %r' % stop_signalling_file)
    exit(1)

lockfile_path = os.path.join(testdir, 'lock_test')
fl = FileLock(lockfile_path, name)

touch_file(stop_signalling_file + '.ready')

with fl:
    while os.path.exists(stop_signalling_file):
        time.sleep(.1)
touch_file(stop_signalling_file + '.done')

# vim: expandtab tabstop=4 shiftwidth=4
