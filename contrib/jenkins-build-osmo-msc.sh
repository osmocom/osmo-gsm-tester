#!/bin/sh
set -e -x
base="$PWD"
name="osmo-msc"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore
build_repo libosmo-abis
build_repo libosmo-netif
build_repo openggsn
build_repo libsmpp34
build_repo libosmo-sccp
build_repo libasn1c
build_repo osmo-iuh neels/sigtran # TEMPORARY BRANCH
build_repo openbsc aoip --enable-smpp --enable-osmo-bsc --enable-nat --enable-iu

create_bin_tgz
