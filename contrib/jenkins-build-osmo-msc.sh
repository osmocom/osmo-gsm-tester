#!/bin/sh
set -e -x

base="$PWD"
prefix="$base/inst-osmo-msc"

rm -f "$base/osmo-msc*.tgz"

git_url="git://git.osmocom.org"

have_repo() {
	repo="$1"
	branch="${2-master}"

	cd "$base"
	if [ ! -d "$repo" ]; then
		git clone "$git_url/$repo" -b "$branch" "$repo"
	fi
	cd "$repo"
	rm -rf *
	git fetch origin
	git checkout .
	git checkout "$branch"
	git reset --hard origin/"$branch"
	git rev-parse HEAD

	cd "$base"
}

build_repo() {
	dep="$1"
	branch="${2-master}"

	have_repo "$dep" "$branch"

	cd "$dep"

	echo "$(git rev-parse HEAD) $dep" >> "$prefix/osmo-msc_git_hashes.txt"

	config_opts=""

	case "$dep" in
	'openbsc')
		config_opts="$config_opts --enable-smpp --enable-osmo-bsc --enable-nat --enable-iu"
		cd openbsc/
	;;
	esac

	autoreconf -fi
	./configure --prefix="$prefix" $config_opts
	make -j8 || make  # libsmpp34 can't build in parallel
	make install
}

rm -rf "$prefix"
mkdir -p "$prefix"

export PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
export LD_LIBRARY_PATH="$prefix/lib"

build_repo libosmocore
build_repo libosmo-abis
build_repo libosmo-netif
build_repo openggsn
build_repo libsmpp34
build_repo libosmo-sccp neels/aoip # TEMPORARY BRANCH
build_repo libasn1c
build_repo osmo-iuh neels/sigtran # TEMPORARY BRANCH
build_repo openbsc aoip

# don't package documentation -- the libosmocore docs can be up to 16 Mb large,
# a significant amount compared to the binaries
rm -rf "$prefix/share/doc/libosmocore"

# build the archive that is going to be copied to the tester
rm "$base"/*.tgz "$base"/*.md5 || true
cd "$prefix"
this="osmo-msc.build-${BUILD_NUMBER-$(date +%Y-%m-%d_%H_%M_%S)}"
tar="${this}.tgz"
tar czf "$base/$tar" *
cd "$base"
md5sum "$tar" > "${this}.md5"
