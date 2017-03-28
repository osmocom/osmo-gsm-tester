#!/bin/sh
# Remove all but the N newest test run dirs (that have been started)

ts_rx_dir="$1"
ts_prep_dir="$2"
if [ -z "$ts_rx_dir" ]; then
	ts_rx_dir="/var/tmp/osmo-gsm-tester"
fi
if [ -z "$ts_prep_dir" ]; then
	ts_prep_dir="/var/tmp/prep-osmo-gsm-tester"
fi

mkdir -p "$ts_prep_dir"

rm_ts() {
	ts_dir="$1"
	ts_name="$(basename "$ts_dir")"
	echo "Removing: $(ls -ld "$ts_dir")"
	# ensure atomic removal, so that the gsm-tester doesn't take it as a
	# newly added dir (can happen when the 'SEEN' marker is removed first).
	mv "$ts_dir" "$ts_prep_dir/"
	rm -rf "$ts_prep_dir/$ts_name"
}

# keep the N newest test session dirs that have been started: find all that
# have been started sorted by time, then discard all but the N newest ones.

for seen in $(ls -1t "$ts_rx_dir"/*/SEEN | tail -n +31); do
	rm_ts "$(dirname "$seen")"
done
