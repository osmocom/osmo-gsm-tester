#!/bin/bash
# This script reads the network type of an Android phone via ADB
# usage: osmo-gsm-tester_androidue_conn_chk.sh $serial $remote_ip $remote_port
serial=$1
remote_ip=$2
remote_port=$3
while true; do
  if [ "${serial}" == "0" ]; then
    # run_type == ssh
    ssh -p "${remote_port}" root@"${remote_ip}" getprop "gsm.network.type"
  else
    # run_type = local
    adb -s "${serial}" shell getprop "gsm.network.type"
  fi
  sleep 1
done
