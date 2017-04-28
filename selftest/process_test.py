#!/usr/bin/env python3

import _prep
import time
import os

from osmo_gsm_tester import process, util, log

tmpdir = util.Dir(util.get_tempdir())

dollar_path = '%s:%s' % (
    os.path.join(os.getcwd(), 'process_test'),
    os.getenv('PATH'))

p = process.Process('foo', tmpdir, ('foo.py', 'arg1', 'arg2'),
                    env={'PATH': dollar_path})

p.launch()
time.sleep(.5)
p.poll()
print('stdout:')
print(p.get_stdout())
print('stderr:')
print(p.get_stderr())

assert not p.terminated()
p.terminate()
assert p.terminated()
print('result: %r' % p.result)

print('stdout:')
print(p.get_stdout())
print('stderr:')
print(p.get_stderr())
print('done.')

test_ssh = True
test_ssh = False
if test_ssh:
    # this part of the test requires ability to ssh to localhost
    p = process.RemoteProcess('ssh-test', '/tmp', os.getenv('USER'), 'localhost', tmpdir,
                              ('ls', '-al'))
    p.launch()
    p.wait()
    assert p.terminated()
    print('stdout:')
    print(p.get_stdout())
    print('stderr:')
    print(p.get_stderr())

# vim: expandtab tabstop=4 shiftwidth=4
