#!/bin/bash
# This script reads the network type of an Android phone via ADB/SSH
# If the first argument (serial) is 0, SSH is used to remotely connect to the phone
# usage: osmo-gsm-tester_androidue_conn_chk.sh $serial $remote_ip $remote_port
#set -x

# check if all parameters have been passed
if ([ ! $3 ])
then
  echo "Please call script with osmo-gsm-tester_androidue_conn_chk.sh $serial $remote_ip $remote_port"
  echo "E.g. ./osmo-gsm-tester_androidue_conn_chk.sh df2df 10.12.1.106 130 10"
  exit
fi

serial=$1
remote_ip=$2
remote_port=$3

echo "Waiting for Android UE to become available .."

# Check adb is available, if needed
if [ "$serial" != "0" ]; then
  if ! [ -x "$(command -v adb)" ]; then
    echo 'Error: adb is not installed.' >&2
    exit 1
  fi
  echo "Using SSH to access device"
fi

while true; do
  if [ "$serial" == "0" ]; then
    # run_type == ssh
    ssh -p "${remote_port}" root@"${remote_ip}" getprop "gsm.network.type"
  else
    # run_type = local
    adb -s "${serial}" shell getprop "gsm.network.type"
  fi
  sleep 1
done