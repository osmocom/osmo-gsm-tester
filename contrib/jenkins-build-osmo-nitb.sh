#!/bin/sh
set -e -x

base="$PWD"
prefix="$base/inst-osmo-nitb"

rm -f "$base/osmo-nitb*.tgz"

deps="
libosmocore
libosmo-abis
libosmo-netif
openggsn
libsmpp34
libosmo-sccp
openbsc
"

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

rm -rf "$prefix"
mkdir -p "$prefix"

export PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
export LD_LIBRARY_PATH="$prefix/lib"

for dep in $deps; do
	have_repo "$dep"
	cd "$dep"
	rm -rf *
	git checkout .

	echo "$(git rev-parse HEAD) $dep" >> "$prefix/osmo-nitb_git_hashes.txt"

	config_opts=""

	case "$dep" in
	'openbsc')
		config_opts="$config_opts --enable-smpp --enable-osmo-bsc --enable-nat"
		cd openbsc/
	;;
	esac

	autoreconf -fi
	./configure --prefix="$prefix" $config_opts
	make -j8 || make  # libsmpp34 can't build in parallel
	make install
done

# build the archive that is going to be copied to the tester
rm "$base"/*.tgz "$base"/*.md5 || true
cd "$prefix"
this="osmo-nitb.build-${BUILD_NUMBER}"
tar="${this}.tgz"
tar czf "$base/$tar" *
cd "$base"
md5sum "$tar" > "${this}.md5"