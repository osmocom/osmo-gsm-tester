#!/bin/sh
set -e -x
base="$PWD"

run_script="osmo-gsm-tester/contrib/jenkins-run.sh"
test -x "$run_script"

cd osmo-gsm-tester
make deps
make check
cd "$base"

PATH="$base/osmo-gsm-tester/src:$PATH" \
  "$run_script"
