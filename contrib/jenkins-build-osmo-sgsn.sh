#!/bin/sh
set -e -x
base="$PWD"
name="osmo-sgsn"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --disable-doxygen
build_repo libosmo-abis
build_repo libosmo-netif --disable-doxygen
build_repo libosmo-sccp
build_repo openggsn
build_repo osmo-sgsn --disable-iu

create_bin_tgz osmo-sgsn
