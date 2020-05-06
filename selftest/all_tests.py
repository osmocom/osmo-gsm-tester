#!/usr/bin/env python3

import os
import sys
import subprocess
import time
import difflib
import argparse
import re

parser = argparse.ArgumentParser()
parser.add_argument('testdir_or_test', nargs='*',
        help='subdir name or test script name')
parser.add_argument('-u', '--update', action='store_true',
        help='Update test expecations instead of verifying them')
args = parser.parse_args()

def run_test(path):
    print(path)
    p = subprocess.Popen(path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    o,e = p.communicate()
    while True:
        retval = p.poll()
        if retval is not None:
            break;
        p.kill()
        time.sleep(.1)
    return retval, o.decode('utf-8'), e.decode('utf-8')

def udiff(expect, got, expect_path):
    expect = expect.splitlines(1)
    got =  got.splitlines(1)
    for line in difflib.unified_diff(expect, got,
                                     fromfile=expect_path, tofile='got'):
        sys.stderr.write(line)
        if not line.endswith('\n'):
            sys.stderr.write('[no-newline]\n')

def verify_output(got, expect_file, update=False):
    if os.path.isfile(expect_file):
        ign_file = expect_file + '.ign'
        if os.path.isfile(ign_file):
            with open(ign_file, 'r') as f:
                ign_rules = f.readlines()
            for ign_rule in ign_rules:
                if not ign_rule:
                    continue
                if '\t' in ign_rule:
                    ign_rule, repl = ign_rule.split('\t')
                    repl = repl.strip()
                else:
                    repl = '*'
                ir = re.compile(ign_rule)
                got = repl.join(ir.split(got))

        if update:
            with open(expect_file, 'w') as f:
                f.write(got)
            return True

        with open(expect_file, 'r') as f:
            expect = f.read()

        if expect != got:
            udiff(expect, got, expect_file)
            sys.stderr.write('output mismatch: %r\n'
                            % os.path.basename(expect_file))
            return False
    return True


script_dir = sys.path[0]

tests = []
for d in os.listdir(script_dir):
    dir_path = os.path.join(script_dir, d)
    if not os.path.isdir(dir_path):
        continue
    if not dir_path.endswith('_test'):
        continue
    for f in os.listdir(dir_path):
        file_path = os.path.join(script_dir, d, f)
        if not os.path.isfile(file_path):
            continue

        if not (file_path.endswith('_test.py') or file_path.endswith('_test.sh')):
            continue
        tests.append(file_path)

ran = []
errors = []

for test in sorted(tests):

    if args.testdir_or_test:
        if not any([t in test for t in args.testdir_or_test]):
            continue

    ran.append(test)

    success = True

    name, ext = os.path.splitext(test)
    ok_file = name + '.ok'
    err_file = name + '.err'

    rc, out, err = run_test(test)

    if rc != 0:
        sys.stderr.write('%r: returned %d\n' % (os.path.basename(test), rc))
        success = False

    if not verify_output(out, ok_file, args.update):
        success = False
    if not verify_output(err, err_file, args.update):
        success = False

    if not success:
        sys.stderr.write('\nTest failed: %r\n\n' % os.path.basename(test))
        errors.append(test)

if errors:
    print('%d of %d TESTS FAILED:\n  %s' % (len(errors), len(ran), '\n  '.join(errors)))
    exit(1)

print('%d tests ok' % len(ran))
exit(0)

# vim: expandtab tabstop=4 shiftwidth=4
