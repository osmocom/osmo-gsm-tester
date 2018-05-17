#!/bin/sh
set -e -x
base="$PWD"
name="osmo-mgw"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --enable-sanitize --disable-doxygen
build_repo libosmo-abis --enable-sanitize
build_repo libosmo-netif --enable-sanitize --disable-doxygen
build_repo osmo-mgw --enable-sanitize

create_bin_tgz "osmo-bsc_mgcp osmo-mgw"
