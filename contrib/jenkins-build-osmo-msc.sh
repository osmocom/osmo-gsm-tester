#!/bin/sh
set -e -x
base="$PWD"
name="osmo-msc"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --disable-doxygen
build_repo libosmo-abis
build_repo libosmo-netif --disable-doxygen
build_repo libsmpp34
build_repo libosmo-sccp
build_repo osmo-mgw
build_repo osmo-msc --enable-smpp --disable-iu

create_bin_tgz osmo-msc
