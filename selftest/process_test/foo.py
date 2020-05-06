#!/usr/bin/env python3

import sys
import atexit
import time
import signal

def signal_handler(sig, frame):
    print('SIGINT received')
    sys.exit(42)

signal.signal(signal.SIGINT, signal_handler)

sys.stdout.write('foo stdout\n')
sys.stderr.write('foo stderr\n')

print(repr(sys.argv))
sys.stdout.flush()
sys.stderr.flush()

def x():
    sys.stdout.write('Exiting (stdout)\n')
    sys.stdout.flush()
    sys.stderr.write('Exiting (stderr)\n')
    sys.stderr.flush()
atexit.register(x)

while True:
    time.sleep(1)

# vim: expandtab tabstop=4 shiftwidth=4
