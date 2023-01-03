#!/bin/sh
set -e -x

base="$PWD"
name="osmocom-bb"
. "$(dirname "$0")/jenkins-build-common.sh"

FW_RPM_URL="http://download.opensuse.org/repositories/home:/mnhauke:/osmocom:/nightly/openSUSE_Tumbleweed/x86_64/"

build_repo libosmocore --disable-doxygen
build_repo libosmo-gprs
build_repo_dir osmocom-bb src/host/virt_phy ${SANITIZE_FLAGS}
build_repo_dir osmocom-bb src/host/osmocon ${SANITIZE_FLAGS}
build_repo_dir osmocom-bb src/host/layer23 ${SANITIZE_FLAGS}

mkdir -p "$prefix"
cd "$prefix"
FW_RPM="$(wget -q -O - "$FW_RPM_URL" | grep -o 'osmocom-bb-firmware.*rpm' | sed 's#\"#\n#g' | head -1)"
echo "Downloading RPM package $FW_RPM"
wget -q "$FW_RPM_URL/$FW_RPM" -O osmocom-bb-firmware.rpm
rpm2cpio osmocom-bb-firmware.rpm  | cpio -idmv
rm osmocom-bb-firmware.rpm

create_bin_tgz "virtphy mobile" "osmocon"
