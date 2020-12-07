#!/bin/sh
set -e -x

_poky_version="$POKY_VERSION"
_poky_path="$POKY_PATH"

[ -z "$_poky_version" ] && _poky_version="2.3.4"
[ -z "$_poky_path" ] && _poky_path="/opt/poky-sdk/$_poky_version"

. "$_poky_path/environment-setup-armv5te-poky-linux-gnueabi"

# Cross-compilation: all installations need to be put in the sysmo SDK sysroot
export DESTDIR="$_poky_path/sysroots/armv5te-poky-linux-gnueabi"

base="$PWD"
name="osmo-pcu-sysmo"
prefix="/usr/local/jenkins-build/inst-$name"
prefix_real="$DESTDIR$prefix"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --disable-pcsc --disable-libmnl --disable-doxygen --disable-gnutls --disable-detect-tls-gcc-arm-bug
build_repo osmo-pcu --enable-sysmocom-dsp

create_bin_tgz osmo-pcu
