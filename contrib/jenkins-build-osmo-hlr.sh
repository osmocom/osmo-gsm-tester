#!/bin/sh
set -e -x
base="$PWD"
name="osmo-hlr"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --disable-doxygen
build_repo libosmo-abis
build_repo osmo-hlr

create_bin_tgz
