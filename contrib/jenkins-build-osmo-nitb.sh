#!/bin/sh
set -e -x
base="$PWD"
name="osmo-nitb"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --disable-doxygen
build_repo libosmo-abis
build_repo libosmo-netif --disable-doxygen
build_repo openggsn
build_repo libsmpp34
build_repo libosmo-sccp
build_repo openbsc --enable-smpp --enable-osmo-bsc --enable-nat

create_bin_tgz osmo-nitb
