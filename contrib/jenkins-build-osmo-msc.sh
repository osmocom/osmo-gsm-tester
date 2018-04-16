#!/bin/sh
set -e -x
base="$PWD"
name="osmo-msc"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --enable-sanitize --disable-doxygen
build_repo libosmo-abis --enable-sanitize
build_repo libosmo-netif --enable-sanitize --disable-doxygen
build_repo libsmpp34 --enable-sanitize
build_repo libosmo-sccp --enable-sanitize
build_repo osmo-mgw --enable-sanitize
build_repo osmo-msc --enable-sanitize --enable-smpp --disable-iu

create_bin_tgz osmo-msc
