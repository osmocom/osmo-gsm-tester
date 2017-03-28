set -e -x

prefix_base="`pwd`"
prefix_dirname="inst-openbsc"
prefix="$prefix_base/$prefix_dirname"

reposes="
libosmocore
libosmo-abis
libosmo-netif
openggsn
libsmpp34
libosmo-sccp
openbsc/openbsc
"

osmo_gsm_tester_host=root@10.9.1.190
osmo_gsm_tester_dir="/var/tmp/osmo-gsm-tester"
tmp_dir="/var/tmp/prep-osmo-gsm-tester"
arch="x86_64"
archive_name="openbsc-$arch-build-$BUILD_NUMBER"
archive="$archive_name.tgz"
manifest="manifest.txt"
test_report="test-report.xml"
test_timeout_sec=120

rm -rf $prefix
mkdir -p $prefix

opt_prefix=""
if [ -n "$prefix" ]; then
        export LD_LIBRARY_PATH="$prefix"/lib
        export PKG_CONFIG_PATH="$prefix"/lib/pkgconfig
        opt_prefix="--prefix=$prefix"
fi

for r in $reposes; do
        make -C "$r" clean || true
done

for r in $reposes; do

        cd "$r"

	echo "$(git rev-parse HEAD) $r" >> "$prefix/openbsc_git_hashes.txt"

        autoreconf -fi

        opt_enable=""
        if [ "$r" = 'openbsc/openbsc' ]; then
                opt_enable="--enable-smpp --enable-osmo-bsc --enable-nat"
        fi

        ./configure "$opt_prefix" $opt_enable

        make -j || make || make
        if [ "$r" != asn1c ]; then
                if [ "$r" = 'libosmo-netif' ]; then
                        # skip clock dependent test in libosmo-netif
                        make check TESTSUITEFLAGS='-k !osmux_test'
                else
                        make check
                fi
        fi
        make install
        cd ..
done

# create test session directory, archive and manifest

cd $prefix_base

ts_name="$NODE_NAME-$BUILD_TAG"
local_ts_base="./compose_ts"
local_ts_dir="$local_ts_base/$ts_name"

rm -rf "$local_ts_base" || true
mkdir -p "$local_ts_dir"

# create archive of openbsc build
tar czf "$local_ts_dir/$archive" "$prefix_dirname"/*
# move archived bts builds into test session directory
mv $WORKSPACE/osmo-bts-*.tgz "$local_ts_dir"
cd "$local_ts_dir"
md5sum *.tgz > $manifest
cd -

# transfer test session directory to temporary dir on osmo-gsm-tester host
# when transfer is complete, move the directory to its final location (where
# the osmo-gsm-tester will recognize the session directory and start the session

ssh $osmo_gsm_tester_host "mkdir -p $tmp_dir"
scp -r "$local_ts_dir" $osmo_gsm_tester_host:$tmp_dir/
ssh $osmo_gsm_tester_host "mv $tmp_dir/$ts_name $osmo_gsm_tester_dir"

# poll for test status
ts_dir="$osmo_gsm_tester_dir/$ts_name"

set +x
ts_log=$ts_dir/test-session.log
echo "Waiting for test session log to be created"
while /bin/true; do
    if ssh $osmo_gsm_tester_host "test -e $ts_log"; then
      break
    fi
    sleep 1
done

echo "Following test session log"
# NOTE this will leave dead ssh session with tail running
ssh $osmo_gsm_tester_host "tail -f $ts_log" &

echo "Waiting for test session to complete"
while /bin/true; do
#    if [ "$test_timeout_sec" = "0" ]; then
#      echo "TIMEOUT test execution timeout ($test_timeout_sec seconds) exceeded!"
#      exit 1
#    fi
    if ssh $osmo_gsm_tester_host "test -e $ts_dir/$test_report";  then
        break
    fi
    sleep 1
#    test_timeout_sec="$(($test_timeout_sec - 1))"
done
set -x

# use pgrep to terminate the ssh/tail (if it still exists)
remote_tail_pid=`ssh $osmo_gsm_tester_host "pgrep -fx 'tail -f $ts_log'"`
echo "remote_tail_pid = $remote_tail_pid"
ssh $osmo_gsm_tester_host "kill $remote_tail_pid"

# copy contents of test session directory back and remove it from the osmo-gsm-tester host

rsync -av -e ssh --exclude='inst-*' --exclude='tmp*' $osmo_gsm_tester_host:$ts_dir/ "$local_ts_dir/"

ssh $osmo_gsm_tester_host "/usr/local/src/osmo-gsm-tester/contrib/ts-dir-cleanup.sh"

# touch test-report.xml (to make up for clock drift between jenkins and build slave)

touch "$local_ts_dir/$test_report"
