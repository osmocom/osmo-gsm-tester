#!/bin/sh
set -e -x
base="$PWD"
name="osmo-hlr"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --enable-sanitize --disable-doxygen
build_repo libosmo-abis --enable-sanitize
build_repo osmo-hlr --enable-sanitize

create_bin_tgz osmo-hlr
