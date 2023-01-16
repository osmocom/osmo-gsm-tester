#!source_this_file

# Common parts for osmo-gsm-tester jenkins build scripts. Use like in below example:
#
#--------------
# #!/bin/sh
# set -e -x
# base="$PWD"
# name="osmo-name"
# . "$(dirname "$0")/jenkins-build-common.sh"
#
# build_repo libosmocore --configure --opts
# build_repo libosmo-foo special_branch --configure --opts
# build_repo osmo-bar
# build_repo_dir openbsc ./openbsc
#
# create_bin_tgz
#--------------
#
# Some explanations:
#
# To allow calling from arbitrary working directories, other scripts should
# source this file like shown above.
#
# Sourcing scripts must provide some variables/functions, see above.
# In addition, these values can optionally be passed to override:
# git_url, prefix, prefix_real, BUILD_NUMBER
#
# CONFIGURE_FLAGS may contain flags that should be passed to all builds'
# ./configure steps (useful e.g. for building in the sysmobts SDK).
#
# For each built repository, a specific git branch or hash can be provided by
# environment variable: OSMO_GSM_TESTER_BUILD_$repo="<git-hash>"
# NOTE: convert $repo's dashes to underscore. For example:
#  OSMO_GSM_TESTER_BUILD_osmo_hlr="f001234abc"
#  OSMO_GSM_TESTER_BUILD_libosmocore="my/branch"
# ("origin/" is prepended to branch names automatically)

if [ -z "$name" -o -z "$base" ]; then
  set +x
  echo "Some environment variables are not provided as required by jenkins-build-common.sh. Error."
  exit 1
fi

git_url="${git_url:-https://git.osmocom.org}"
prefix="${prefix:-$base/inst-$name}"
# prefix_real is usually identical with prefix, except when installing to a
# different $DESTDIR than /, which is the case for example when building
# osmo-bts within the sysmoBTS SDK
prefix_real="${prefix_real:-$prefix}"

# Flag to be used to enable ASAN in builds. Defaults to enable ASAN builds and
# it can be disabled by passing SANITIZE_FLAGS="" to the build.
SANITIZE_FLAGS="${SANITIZE_FLAGS:---enable-sanitize}"

export PKG_CONFIG_PATH="$prefix_real/lib/pkgconfig:$PKG_CONFIG_PATH"
export LD_LIBRARY_PATH="$prefix_real/lib:$LD_LIBRARY_PATH"

# Show current environment. Sometimes the LESS_ vars have ansi colors making a
# mess, so exclude those.
env | grep -v "^LESS" | sort

# clean the workspace
rm -f "$base"/*.build-*.tgz
rm -f "$base"/*.build-*.md5
rm -rf "$prefix_real"
mkdir -p "$prefix_real"

have_repo() {
  repo="$1"
  branch="${2-master}"

  # Evaluate environment for instructions to build a specific git hash.
  # Using a hash as $branch above unfortunately doesn't work.
  branch_override_var="$(echo "OSMO_GSM_TESTER_BUILD_$repo" | sed 's/-/_/g')"
  branch_override="$(eval "echo \$$branch_override_var")"
  if [ -n "$branch_override" ]; then
    branch="$branch_override"
  fi

  cd "$base"
  if [ -d "$repo" ]; then
    cd "$repo"
    git fetch
  else
    git clone "$git_url/$repo" "$repo"
    cd "$repo"
  fi


  # Figure out whether we need to prepend origin/ to find branches in upstream.
  # Doing this allows using git hashes instead of a branch name.
  if git rev-parse "origin/$branch"; then
    branch="origin/$branch"
  fi

  git checkout -B build_branch "$branch"
  rm -rf *
  git reset --hard "$branch"

  git rev-parse HEAD

  echo "$(git rev-parse HEAD) $repo" >> "$prefix_real/${name}_git_hashes.txt"

  git submodule update --init

  cd "$base"
}

build_repo() {
  # usage: build_repo <name> [<branch>] [--configure-opts [...]]
  dir="$1"
  shift
  build_repo_dir "${dir}" "./" $@
}

build_repo_dir() {
  # usage: build_repo_dir <name> <dir> [<branch>] [--configure-opts [...]]
  dep="$1"
  dir="$2"
  branch="master"
  if [ -z "$(echo "$3" | grep '^-')" ]; then
    # second arg does not start with a dash, it's empty or a branch
    branch="$3"
    if [ -n "$branch" ]; then
      # we had a branch arg, need to shift once more to get config options
      shift
    else
      branch="master"
    fi
  fi
  shift
  shift
  configure_opts="$@"

  set +x; echo "

====================== $dep

"; set -x


  have_repo "$dep" "$branch"

  cd "$dep/${dir}"

  if [ -f configure.ac ]; then
    set +x; echo; echo; set -x
    autoreconf -fi
    set +x; echo; echo; set -x
    ./configure --prefix="$prefix" --with-systemdsystemunitdir=no $CONFIGURE_FLAGS $configure_opts
  elif [ -f CMakeLists.txt ]; then
    rm -rf build && mkdir build && cd build || exit 1
    set +x; echo; echo; set -x
    cmake -DCMAKE_INSTALL_PREFIX=$prefix $configure_opts ../
  elif [ -f meson.build ]; then
    rm -rf build && mkdir build && cd build || exit 1
    set +x; echo; echo; set -x
    meson ../ --prefix=$prefix --libdir="lib" $configure_opts
    ninja -j8
    ninja install
    return
  else
    echo "Unknwown build system" && exit 1
  fi
  set +x; echo; echo; set -x
  make -j8 || make  # libsmpp34 can't build in parallel
  set +x; echo; echo; set -x
  make install
}

prune_files() {
        bindir="$1"
        wanted_binaries="$2"

        if [ ! -d "$prefix_real/$bindir" ]; then return; fi
        # remove binaries not intended to originate from this build
        cd "$prefix_real/$bindir"
        for f in * ; do
          if [ -z "$(echo "_ $wanted_binaries _" | grep " $f ")" ]; then
            rm "$f"
          fi
        done

        # ensure requested binaries indeed exist
        for b in $wanted_binaries ; do
          if [ ! -f "$b" ]; then
            set +x; echo "ERROR: no such binary: $b in $prefix_real/$bindir/"; set -x
            ls -1 "$prefix_real/$bindir"
            exit 1
          fi
        done
}

add_rpath() {
	# Adds an RPATH to executables in bin/ or sbin/ to search for the
	# (Osmocom) libraries in `dirname /proc/self/exe`/../lib/. Adds an
	# RPATH to a library to search in the same directory as the library.
	#
	# NOTE: Binaries should not have the SUID bit set and should run as the
	# user executing the binary.
	#
	# NOTE: $ORIGIN is not a shell variable but a feature of the dynamic
	# linker that will be expanded at runtime. For details see:
	# http://man7.org/linux/man-pages/man8/ld.so.8.html
	#
	# Add an rpath relative to the binary and library if the directory
	# exists.

  rpath_args='--set-rpath'
  rpath_dir='$ORIGIN/../lib/'
  if [ -n "$patchelf_rapth_extra_args" ]; then
    rpath_args="$patchelf_rapth_extra_args $rpath_args"
  fi

  if [ -n "$patchelf_rpath_dir" ]; then
    rpath_dir="$rpath_dir:$patchelf_rpath_dir"
  fi

	if [ -d bin/ ]; then
		find bin -depth -type f -exec patchelf $rpath_args "$rpath_dir" {} \;
	fi
	if [ -d sbin/ ]; then
		find sbin -depth -type f -exec patchelf $rpath_args "$rpath_dir" {} \;
	fi
	if [ -d lib/ ]; then
		find lib -depth -type f -name "lib*.so.*" -exec patchelf --set-rpath '$ORIGIN/' {} \;
	fi
}

create_bin_tgz() {
  # build the archive that is going to be copied to the tester

  wanted_binaries_bin="$1"
  wanted_binaries_sbin="$2"

  if [ -z "$wanted_binaries_bin" ] && [ -z "$wanted_binaries_sbin" ]; then
    set +x; echo "ERROR: create_bin_tgz needs a list of permitted binaries"; set -x
    exit 1
  fi

  prune_files bin "$wanted_binaries_bin"
  prune_files sbin "$wanted_binaries_sbin"
  # Drop all static libraries if exist:
  rm -f $prefix_real/lib/*.a
  rm -f $prefix_real/lib/*.la

  cd "$prefix_real"
  add_rpath
  this="$name.build-${BUILD_NUMBER-$(date +%Y-%m-%d_%H_%M_%S)}"
  tar="${this}.tgz"
  tar czf "$base/$tar" *
  cd "$base"
  md5sum "$tar" > "${this}.md5"
}
