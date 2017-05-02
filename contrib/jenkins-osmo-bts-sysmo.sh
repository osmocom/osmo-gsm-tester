#!/bin/sh
set -e -x

deps="
libosmocore
libosmo-abis
osmo-bts
"

base="$PWD"
rm -f "$base/osmo-bts-sysmo.*.tgz"

have_repo() {
	repo="$1"
	cd "$base"
	if [ ! -e "$repo" ]; then
		set +x
		echo "MISSING REPOSITORY: $repo"
		echo "should be provided by the jenkins workspace"
		exit 1
	fi
	cd "$repo"
	git clean -dxf
	cd "$base"
}

for dep in $deps; do
    have_repo "$dep"
done

# for gsm_data_shared.h
have_repo openbsc

. /opt/poky/1.5.4/environment-setup-armv5te-poky-linux-gnueabi

# Cross-compilation: all installations need to be put in the sysmo SDK sysroot
export DESTDIR=/opt/poky/1.5.4/sysroots/armv5te-poky-linux-gnueabi

prefix_base="/usr/local/jenkins-build"
prefix_base_real="$DESTDIR$prefix_base"
rm -rf "$prefix_base_real"

prefix="$prefix_base/inst-osmo-bts-sysmo"
prefix_real="$DESTDIR$prefix"
mkdir -p "$prefix_real"

for dep in $deps; do
        cd "$base/$dep"
        rm -rf *
        git checkout .

        echo "$(git rev-parse HEAD) $dep" >> "$prefix_real/osmo-bts-sysmo_git_hashes.txt"

        autoreconf -fi

        config_opts=""
        case "$dep" in
        'libosmocore')    config_opts="--disable-pcsc" ;;
        'osmo-bts')       config_opts="--enable-sysmocom-bts --with-openbsc=$base/openbsc/openbsc/include" ;;
        esac

        ./configure --prefix="$prefix" $CONFIGURE_FLAGS $config_opts
        make -j8
        make install
done

# build the archive that is going to be copied to the tester and then to the BTS
rm "$base"/*.tgz || true
cd "$prefix_real"
tar cvzf "$base/osmo-bts-sysmo.build-${BUILD_NUMBER}.tgz" *
