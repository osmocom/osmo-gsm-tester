#!/bin/sh
set -e -x

_poky_version="$POKY_VERSION"
_poky_path="$POKY_PATH"

[ -z "$_poky_version" ] && _poky_version="1.5.4"
[ -z "$_poky_path" ] && _poky_path="/opt/poky/$_poky_version"

. "$_poky_path/environment-setup-armv5te-poky-linux-gnueabi"

# Cross-compilation: all installations need to be put in the sysmo SDK sysroot
export DESTDIR="$_poky_path/sysroots/armv5te-poky-linux-gnueabi"

base="$PWD"
name="osmo-bts-sysmo"
prefix="/usr/local/jenkins-build/inst-$name"
prefix_real="$DESTDIR$prefix"
. "$(dirname "$0")/jenkins-build-common.sh"

# for gsm_data_shared.h
have_repo openbsc

build_repo libosmocore --disable-pcsc --disable-doxygen --disable-gnutls
build_repo libosmo-abis
build_repo osmo-bts --enable-sysmocom-bts --with-openbsc=$base/openbsc/openbsc/include

create_bin_tgz osmo-bts-sysmo
