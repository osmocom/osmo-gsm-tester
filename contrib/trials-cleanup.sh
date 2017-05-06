#!/bin/sh
# Remove all but the N newest test run dirs (that have been started)

trial_rx_dir="$1"
trial_prep_dir="$2"
if [ -z "$trial_rx_dir" ]; then
	trial_rx_dir="/var/tmp/osmo-gsm-tester"
fi
if [ -z "$trial_prep_dir" ]; then
	trial_prep_dir="/var/tmp/prep-osmo-gsm-tester"
fi

mkdir -p "$trial_prep_dir"

rm_trial() {
	trial_dir="$1"
	trial_name="$(basename "$trial_dir")"
	echo "Removing: $(ls -ld "$trial_dir")"
	# ensure atomic removal, so that the gsm-tester doesn't take it as a
	# newly added dir (can happen when the 'taken' marker is removed first).
	mv "$trial_dir" "$trial_prep_dir/"
	rm -rf "$trial_prep_dir/$trial_name"
}

# keep the N newest test session dirs that have been started: find all that
# have been started sorted by time, then discard all but the N newest ones.

for seen in $(ls -1t "$trial_rx_dir"/*/taken | tail -n +31); do
	rm_trial "$(dirname "$seen")"
done
