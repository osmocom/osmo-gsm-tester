#!/bin/sh
set -e -x

if [ -z "$OSMO_GSM_TESTER_REMOTE_MAIN_UNIT" ]; then
  echo "To run the tests from jenkins, a main unit host must be defined."
  echo "e.g. OSMO_GSM_TESTER_REMOTE_MAIN_UNIT=\"user@10.9.8.7\""
fi

osmo_gsm_tester_host="$OSMO_GSM_TESTER_REMOTE_MAIN_UNIT"
osmo_gsm_tester_src="${OSMO_GSM_TESTER_REMOTE_SRC:-/usr/local/src/osmo-gsm-tester}"

if ssh "$osmo_gsm_tester_host" "test -d \"$osmo_gsm_tester_src\"" ; then
  # exists
  status="$(ssh "$osmo_gsm_tester_host" "git -C \"$osmo_gsm_tester_src\" status --porcelain")"
  if [ "x$status" != "x" ]; then
    echo "Remote osmo-gsm-tester is not clean: $osmo_gsm_tester_host:$osmo_gsm_tester_src"
    echo "$status"
    exit 1
  fi
  ssh "$osmo_gsm_tester_host" "cd \"$osmo_gsm_tester_src\"; git clean -fdx; git pull"
else
  osmo_gsm_tester_src_dirname="$(dirname "$osmo_gsm_tester_src")"
  ssh "$osmo_gsm_tester_host" "git clone git://git.osmocom.org/osmo-gsm-tester.git \"$osmo_gsm_tester_src\""
fi
