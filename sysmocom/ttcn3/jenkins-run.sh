#!/bin/sh
set -e -x
base="$PWD"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P) # this file's directory
OSMO_GSM_TESTER_CONF=${OSMO_GSM_TESTER_CONF:-${SCRIPT_DIR}/main.conf}

time_start="$(date '+%F %T')"

prepare_docker() {
        OLDPWD=$PWD

        # update docker-playground and update the BSC and bsc-test containers (if needed)
        DIR=~/jenkins/docker-playground
        if [ ! -d "$DIR" ]; then
                mkdir -p ~/jenkins/ && cd ~/jenkins
                git clone git://git.osmocom.org/docker-playground
        fi
        cd $DIR
        git remote prune origin; git fetch; git checkout -f -B master origin/master
        cd $DIR/debian-stretch-titan && make
        docker pull laforge/debian-stretch-titan:latest # HACK
        cd $DIR/ttcn3-bts-test && make
        # execute the script to start containers, read results, ...
        #cd $DIR/ttcn3-bts-test && sh -x ./jenkins.sh
        PWD=$OLDPWD
}

docker pull registry.sysmocom.de/ttcn3-bts-test

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
journalctl -u ofono -o short-precise --since "${time_start}" > "$(readlink last_run)/ofono.log"
tar czf "$base/${trial_dir}-run.tgz" "$(readlink last_run)"
tar czf "$base/${trial_dir}-bin.tgz" *.md5 *.tgz

exit $exit_code
