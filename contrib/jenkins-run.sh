#!/bin/sh
set -e -x

if [ -z "$OSMO_GSM_TESTER_REMOTE_MAIN_UNIT" ]; then
  echo "To run the tests from jenkins, a main unit host must be defined."
  echo "e.g. OSMO_GSM_TESTER_REMOTE_MAIN_UNIT=\"user@10.9.8.7\""
fi

osmo_gsm_tester_host="$OSMO_GSM_TESTER_REMOTE_MAIN_UNIT"
osmo_gsm_tester_src="${OSMO_GSM_TESTER_REMOTE_SRC:-/usr/local/src/osmo-gsm-tester}"
osmo_gsm_tester_dir="/var/tmp/osmo-gsm-tester/trials"
tmp_dir="/var/tmp/osmo-gsm-tester/.prep-trials"

#trial_name="$NODE_NAME-$BUILD_TAG"
trial_name="trial-$BUILD_NUMBER"
local_trial_base="./compose_trial"
local_trial_dir="$local_trial_base/$trial_name"

rm -rf "$local_trial_base" || true
mkdir -p "$local_trial_dir"

# Add archives from other jenkins builds.
# This jenkins job must be configured to copy *.tgz artifacts to the
# workspace from the various jenkins*bts*.sh runs.
mv $WORKSPACE/*.tgz "$local_trial_dir"
cd "$local_trial_dir"
md5sum *.tgz > checksums.md5
cd -

ssh "$osmo_gsm_tester_host" "$osmo_gsm_tester_src/contrib/trials-cleanup.sh"

ssh "$osmo_gsm_tester_host" "mkdir -p $tmp_dir"
scp -r "$local_trial_dir" $osmo_gsm_tester_host:$tmp_dir/
ssh "$osmo_gsm_tester_host" "mv $tmp_dir/$trial_name $osmo_gsm_tester_dir"
trial_dir="$osmo_gsm_tester_dir/$trial_name"

ssh "$osmo_gsm_tester_host" "python3 -u $osmo_gsm_tester_src/src/osmo-gsm-tester.py $trial_dir -T $OSMO_GSM_TESTER_OPTS"
