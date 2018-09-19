#!/bin/sh
set -e -x
base="$PWD"
name="osmo-sgsn"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --enable-sanitize --disable-doxygen
build_repo libosmo-abis --enable-sanitize
build_repo libosmo-netif --enable-sanitize --disable-doxygen
build_repo libosmo-sccp --enable-sanitize
build_repo osmo-ggsn --enable-sanitize
build_repo libasn1c --enable-sanitize
build_repo osmo-iuh --enable-sanitize
build_repo osmo-sgsn --enable-sanitize --enable-iu

create_bin_tgz osmo-sgsn
