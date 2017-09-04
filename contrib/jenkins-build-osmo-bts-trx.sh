#!/bin/sh
set -e -x
base="$PWD"
name="osmo-bts-trx"
. "$(dirname "$0")/jenkins-build-common.sh"

# for gsm_data_shared.*
have_repo openbsc

build_repo libosmocore --disable-doxygen
build_repo libosmo-abis
build_repo osmo-bts --enable-trx --with-openbsc=$base/openbsc/openbsc/include

create_bin_tgz osmo-bts-trx
