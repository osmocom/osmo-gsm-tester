set -x -e

base="$PWD"
inst="inst-osmo-bts-trx"
prefix="$base/$inst"

deps="
libosmocore
libosmo-abis
osmo-trx
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


rm -rf "$prefix"
mkdir -p "$prefix"

export PKG_CONFIG_PATH="$prefix/lib/pkgconfig"
export LD_LIBRARY_PATH="$prefix/lib"

for dep in $deps; do
	have_repo "$dep"
	cd "$dep"

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
rm -f "$base/osmo-bts-trx*.tgz"
cd "$base"
tar czf "osmo-bts-trx.build-${BUILD_NUMBER}.tgz" "$inst"
