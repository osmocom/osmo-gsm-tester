#!/bin/sh
set -e -x
base="$PWD"
name="osmo-bsc"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --enable-sanitize --disable-doxygen
build_repo libosmo-abis --enable-sanitize
build_repo libosmo-netif --enable-sanitize --disable-doxygen
build_repo libosmo-sccp --enable-sanitize
build_repo osmo-mgw --enable-sanitize
build_repo osmo-bsc --enable-sanitize

create_bin_tgz "osmo-bsc abisip-find ipaccess-config"
