#!/bin/sh -ex
# environment variables:
# * PUBLISH: upload manuals after building if set to "1"

base="$PWD"
export OSMO_GSM_MANUALS_DIR="$base/osmo-gsm-manuals"

# Sanity check
if ! [ -d "$base/doc/manuals" ]; then
	echo "ERROR: this script needs to be executed from the top dir of osmo-gsm-tester.git."
	exit 1
fi

# Clone/update osmo-gsm-manuals and wipe local modifications
if [ -d "$OSMO_GSM_MANUALS_DIR" ]; then
	git -C "$OSMO_GSM_MANUALS_DIR" pull
else
	git clone "https://git.osmocom.org/osmo-gsm-manuals" "$OSMO_GSM_MANUALS_DIR"
fi
git -C "$OSMO_GSM_MANUALS_DIR" checkout -f HEAD

# Copy manuals source to empty temp dir (so we can easily clean up afterwards)
temp="$base/_manuals_temp"
if [ -d "$temp" ]; then
	rm -rf "$temp"
fi
cp -r "$base/doc/manuals" "$temp"

# Build the manuals
cd "$temp"
make
make check

# Publish
if [ "$PUBLISH" = "1" ]; then
	make publish
fi

# Clean up
rm -r "$temp"
