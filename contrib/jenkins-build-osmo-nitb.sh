#!/bin/sh
set -e -x
base="$PWD"
name="osmo-nitb"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --disable-doxygen --disable-uring
build_repo libosmo-abis --disable-dahdi
build_repo libosmo-netif --disable-doxygen
build_repo openggsn
build_repo libsmpp34
build_repo libosmo-sigtran
build_repo_dir openbsc openbsc --enable-smpp --enable-osmo-bsc --enable-nat

create_bin_tgz "osmo-nitb osmo-bsc_mgcp"
