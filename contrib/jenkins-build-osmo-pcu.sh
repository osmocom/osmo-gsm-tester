#!/bin/sh
set -e -x
base="$PWD"
name="osmo-pcu"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --enable-sanitize --disable-pcsc --disable-doxygen
build_repo osmo-pcu --enable-sanitize

create_bin_tgz osmo-pcu
