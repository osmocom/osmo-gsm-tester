#!/usr/bin/env python3

import time
import _prep
import os
from osmo_gsm_tester.core import util
from osmo_gsm_tester.core.trial import Trial

workdir = util.get_tempdir()

trials_dir = util.Dir(workdir)

print('- make a few trials dirs')
print(trials_dir.mkdir('first'))
time.sleep(1)
print(trials_dir.mkdir('second'))
time.sleep(1)
print(trials_dir.mkdir('third'))

print('- fetch trial dirs in order')
t = Trial.next(trials_dir)
print(t)
print(repr(sorted(t.dir.children())))
print(Trial.next(trials_dir))
print(Trial.next(trials_dir))

print('- no more trial dirs left')
print(repr(Trial.next(trials_dir)))

print('- test checksum verification')
d = util.Dir('trial_test')
t = Trial(d.child('valid_checksums'))
t.verify()

print('- detect wrong checksum')
t = Trial(d.child('invalid_checksum'))
try:
    t.verify()
except RuntimeError as e:
    print('ok, got RuntimeError: %s' % str(e))

print('- detect missing file')
t = Trial(d.child('missing_file'))
try:
    t.verify()
except RuntimeError as e:
    print('ok, got RuntimeError: %s' % str(e))

# vim: expandtab tabstop=4 shiftwidth=4
