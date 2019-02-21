#!/bin/sh
set -e -x
base="$PWD"

time_start="$(date '+%F %T')"

# remove older trial dirs and *-run.tgz, if any
trial_dir_prefix="trial-"
rm -rf "$trial_dir_prefix"* || true

# Expecting *.tgz artifacts to be copied to this workspace from the various
# jenkins-*.sh runs, via jenkins job configuration. Compose a trial dir:
trial_dir="${trial_dir_prefix}$BUILD_NUMBER"
mkdir -p "$trial_dir"

mv *.tgz "$trial_dir"
cat *.md5 >> "$trial_dir/checksums.md5"
rm *.md5

# OSMO_GSM_TESTER_OPTS is a way to pass in e.g. logging preferences from the
# jenkins build job.
# On failure, first clean up below and then return the exit code.
exit_code="1"
if python3 -u "$(which osmo-gsm-tester.py)" "$trial_dir" $OSMO_GSM_TESTER_OPTS ; then
  exit_code="0"
fi

# no need to keep extracted binaries
rm -rf "$trial_dir/inst" || true

# tar up all results for archiving (optional)
cd "$trial_dir"
if [ -x $(command -v journalctl) ]; then
  journalctl -u ofono -o short-precise --since "${time_start}" > "$(readlink last_run)/ofono.log"
fi
tar czf "$base/${trial_dir}-run.tgz" "$(readlink last_run)"
tar czf "$base/${trial_dir}-bin.tgz" *.md5 *.tgz

exit $exit_code
