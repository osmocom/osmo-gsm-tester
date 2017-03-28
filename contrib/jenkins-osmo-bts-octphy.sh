#!/bin/sh

set -e

OPTION_DO_CLONE=0
OPTION_DO_CLEAN=0
OPTION_DO_TEST=1

PREFIX=`pwd`/inst-osmo-bts-octphy

# NOTE Make sure either 'octphy-2g-headers' (prefered) or
# 'octsdr-2g' is listed among the repositories

octbts_repos="libosmocore
libosmo-abis
openbsc/openbsc
octphy-2g-headers
osmo-bts"

clone_repos() {
	repos="$1"
	for repo in $repos; do
		if [ -e $repo ]; then
			continue
		fi
		if [ "$repo" = "libosmocore" ]; then
			url="git://git.osmocom.org/libosmocore.git"
		elif [ "$repo" = "libosmo-abis" ]; then
			url="git://git.osmocom.org/libosmo-abis.git"
		elif [ "$repo" = "libosmo-netif" ]; then
			url="git://git.osmocom.org/libosmo-netif.git"
		elif [ "$repo" = "openbsc/openbsc" ]; then
			url="git://git.osmocom.org/openbsc"
		elif [ "$repo" = "octphy-2g-headers" ]; then
			url="git://git.osmocom.org/octphy-2g-headers"
		elif [ "$repo" = "octsdr-2g" ]; then
			# NOTE acutally we only need the headers from the octphy-2g-headers
			# repository but this (private) repository contains more recent versions
			url="ssh://git@git.admin.sysmocom.de/octasic/octsdr-2g"
		elif [ "$repo" = "osmo-bts" ]; then
			url="git://git.osmocom.org/osmo-bts.git"
		else
			exit 2
		fi
		git clone $url
	done
}

main() {
	repos="$1"
	if [ $OPTION_DO_CLONE -eq 1 ]; then	clone_repos "$repos"; fi
	rm -rf $PREFIX
	mkdir -p $PREFIX
	for repo in $repos; do
		if [ "$repo" = "openbsc/openbsc" ]; then
			continue
		fi
		if [ "$repo" = "octphy-2g-headers" ]; then
			OCTPHY_INCDIR=`pwd`/octphy-2g-headers
			continue
		fi
		if [ "$repo" = "octsdr-2g" ]; then
			cd $repo
			git checkout 5c7166bab0a0f2d8a9664213d18642ae305e7004
			cd -
			OCTPHY_INCDIR=`pwd`/octsdr-2g/software/include
			continue
		fi
		cd $repo
		if [ $OPTION_DO_CLEAN  -eq 1 ]; then	git clean -dxf; fi
		echo "$(git rev-parse HEAD) $repo" >> "$PREFIX/osmo-bts-octphy_git_hashes.txt"
		autoreconf -fi
		if [ "$repo" != "libosmocore" ]; then
			export PKG_CONFIG_PATH=$PREFIX/lib/pkgconfig
			export LD_LIBRARY_PATH=$PREFIX/lib:/usr/local/lib
		fi
		config_opts=""
		case "$repo" in
		'osmo-bts')	config_opts="$config_opts --enable-octphy --with-octsdr-2g=$OCTPHY_INCDIR"
		esac
		./configure --prefix=$PREFIX $config_opts
		make -j8
		if [ $OPTION_DO_TEST -eq 1 ]; then	make check; fi
		make install
		cd ..
	done
}

set -x
main "$octbts_repos"

# build the archive that is going to be copied to the tester and then to the BTS
rm -f $WORKSPACE/osmo-bts-octphy*.tgz
tar czf $WORKSPACE/osmo-bts-octphy-build-$BUILD_NUMBER.tgz inst-osmo-bts-octphy
