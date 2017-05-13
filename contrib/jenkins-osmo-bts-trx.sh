#!/bin/sh
set -x -e

base="$PWD"
prefix="$base/inst-osmo-bts-trx"

rm -f "$base/osmo-bts-trx*.tgz"

deps="
libosmocore
libosmo-abis
osmo-trx
osmo-bts
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

# for gsm_data_shared.*
have_repo openbsc


rm -rf "$prefix"
mkdir -p "$prefix"

export PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
export LD_LIBRARY_PATH="$prefix/lib"

for dep in $deps; do
	have_repo "$dep"
	cd "$dep"
	rm -rf *
	git checkout .

	echo "$(git rev-parse HEAD) $dep" >> "$prefix/osmo-bts-trx_osmo-trx_git_hashes.txt"

	autoreconf -fi

	config_opts=""

	case "$repo" in
	'osmo-bts') config_opts="--enable-trx --with-openbsc=$base/openbsc/openbsc/include" ;;
	'osmo-trx') config_opts="--without-sse" ;;
	esac

	./configure --prefix="$prefix" $config_opts
	make -j8
	make install
done

# build the archive that is going to be copied to the tester
rm "$base"/*.tgz "$base"/*.md5 || true
cd "$prefix"
this="osmo-bts-trx.build-${BUILD_NUMBER}"
tar="${this}.tgz"
tar czf "$base/$tar" *
cd "$base"
md5sum "$tar" > "${this}.md5"
