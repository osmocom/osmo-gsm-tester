#!/bin/bash
# This script pulls the diag folder created by diag_mdlog and parses the
# .qmdl file. Further, it writes all packets to a pcap file.
# usage: osmo-gsm-tester_androidue_diag_parser.sh $serial $run_dir $pcap_path $remote_ip $remote_port
serial=$1
run_dir=$2
pcap_path=$3
remote_ip=$4
remote_port=$5
while true; do
  echo "Pulling new .qmdl file..."
  if [ "${remote_ip}" == "0" ]; then
    # ScatParser and AndroidUe are attached to/running on the same machine
    sudo adb -s "${serial}" pull /data/local/tmp/diag_logs "${run_dir}" >/dev/null
    wait $!
  else
    # ScatParser and AndroidUe are attached to/running on different machines
    scp -r -P "${remote_port}" root@"${remote_ip}":/data/local/tmp/diag_logs/ "${run_dir}"
    wait $!
  fi
  qmdl_fn=$(find "${run_dir}" -maxdepth 2 -type f -name "*.qmdl")
  wait $!
  sudo scat -t qc --event -d "${qmdl_fn}" -F "${pcap_path}"
  wait $!
done
