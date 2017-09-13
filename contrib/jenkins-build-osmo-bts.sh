#!/bin/sh
set -e -x
base="$PWD"
name="osmo-bts"
. "$(dirname "$0")/jenkins-build-common.sh"

# for gsm_data_shared.*
have_repo openbsc
have_repo octphy-2g-headers

build_repo libosmocore --disable-doxygen
build_repo libosmo-abis
build_repo osmo-bts --enable-trx --with-openbsc=$base/openbsc/openbsc/include --enable-octphy --with-octsdr-2g=$base/octphy-2g-headers

create_bin_tgz osmo-bts-trx osmo-bts-octphy
