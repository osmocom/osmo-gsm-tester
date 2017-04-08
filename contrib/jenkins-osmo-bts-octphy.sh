#!/bin/sh
set -x -e

base="$PWD"
prefix="$base/inst-osmo-bts-octphy"

rm -f "$base/osmo-bts-octphy*.tgz"

deps="
libosmocore
libosmo-abis
osmo-bts
"

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

# for gsm_data_shared.*
have_repo openbsc

# octphy headers
have_repo octphy-2g-headers


rm -rf "$prefix"
mkdir -p "$prefix"

export PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
export LD_LIBRARY_PATH="$prefix/lib"

for dep in $deps; do
	have_repo "$dep"
	cd "$dep"
	rm -rf *
	git checkout .

	echo "$(git rev-parse HEAD) $dep" >> "$prefix/osmo-bts-octphy_git_hashes.txt"

	autoreconf -fi

	config_opts=""

	case "$repo" in
	'osmo-bts')	config_opts="$config_opts --enable-octphy --with-octsdr-2g=$base/octphy-2g-headers" ;;
	esac

	./configure --prefix="$prefix" $config_opts
	make -j8
	make install
done

# build the archive that is going to be copied to the tester
cd "$prefix"
tar czf "$base/osmo-bts-octphy.build-${BUILD_NUMBER}.tgz" *