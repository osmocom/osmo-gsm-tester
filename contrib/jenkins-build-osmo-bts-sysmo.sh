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
	if [ ! -d "$repo" ]; then
		git clone "git://git.osmocom.org/$repo" "$repo"
	fi
	cd "$repo"
	git clean -dxf
	git fetch origin
	git reset --hard origin/master
	git rev-parse HEAD
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

# Installation in non-system dir, but keep the PKG_CONFIG_PATH from the SDK:
export PKG_CONFIG_PATH="$prefix_real/lib/pkgconfig:$PKG_CONFIG_PATH"

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

# don't package documentation -- the libosmocore docs can be up to 16 Mb large,
# a significant amount compared to the binaries
rm -rf "$prefix_real/share/doc/libosmocore"

# build the archive that is going to be copied to the tester and then to the BTS
rm "$base"/*.tgz "$base"/*.md5 || true
cd "$prefix_real"
this="osmo-bts-sysmo.build-${BUILD_NUMBER}"
tar="${this}.tgz"
tar czf "$base/$tar" *
cd "$base"
md5sum "$tar" > "${this}.md5"
