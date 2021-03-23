#!/bin/sh
set -e -x

amarisoft_tgz="$1"

BUILD_AMARISOFT_TRX_ZMQ="${BUILD_AMARISOFT_TRX_ZMQ:-1}"
HAVE_AMARISOFT_LTEUE="${HAVE_AMARISOFT_LTEUE:-1}"

if [ ! -f "$amarisoft_tgz" ]; then
        echo "Amarisoft tgz doesn't exist: $amarisoft_tgz"
        exit 1
fi

base="$PWD"
if [ "x${BUILD_AMARISOFT_TRX_ZMQ}" = "x1" ]; then
        name="srslte"
        git_url="${git_url:-https://github.com/srsLTE}"
        project_name_srslte="${project_name:-srsLTE}"
        branch="master"
        . "$(dirname "$0")/jenkins-build-common.sh"

        #TODO: make sure libconfig, zeroMQ is installed
        build_repo $project_name_srslte $branch -DENABLE_UHD=False -DENABLE_BLADERF=False -DENABLE_SOAPYSDR=False -DENABLE_ZEROMQ=True

        git_url="git@github.com:softwareradiosystems"
        project_name_zmq="amarisoft_dummy_trx"
        branch="trx_zmq"
        have_repo $project_name_zmq $branch
        cd $project_name_zmq
        rm -rf build && mkdir build && cd build || exit 1
        cmake -DSRSLTE_BUILD_PATH=${base}/${project_name_srslte}/build ../
        make -j8
        cd $base
fi

rm -rf inst-tmp && mkdir inst-tmp
rm -rf inst-tmp-uhd && mkdir inst-tmp-uhd
tar -zxf $amarisoft_tgz -C inst-tmp/
for file in inst-tmp/*/trx_uhd*.tar.gz; do tar -zxf "$file" -C inst-tmp/; done

# Build trx_uhd.so:
for path in ${base}/inst-tmp/trx_uhd-linux*/; do (cd "$path"; make; cd ${base}); done

# Create amarisoftenb inst:
rm -rf inst-amarisoftenb && mkdir inst-amarisoftenb || exit 1
tar --strip-components=1 -zxf inst-tmp/*/lteenb-linux*.tar.gz -C inst-amarisoftenb/
if [ "x${BUILD_AMARISOFT_TRX_ZMQ}" = "x1" ]; then
        cp ${base}/${project_name_srslte}/build/lib/src/phy/rf/libsrsran_rf.so inst-amarisoftenb/
        cp ${base}/${project_name_zmq}/build/libtrx_zmq-linux-2021-03-15.so inst-amarisoftenb/trx_zmq.so
        patchelf --set-rpath '$ORIGIN/' inst-amarisoftenb/trx_zmq.so
        cd inst-amarisoftenb && ln -s libsrsran_rf.so libsrsran_rf.so.0 && cd ..
fi

# Untar trx_sdr and copy the libraries to enb.
tar -xzf inst-tmp/*/trx_sdr*.tar.gz -C inst-tmp/
cp ${base}/inst-tmp/trx_sdr-linux-2021-03-15/trx_sdr.so inst-amarisoftenb/
cp ${base}/inst-tmp/trx_sdr-linux-2021-03-15/libsdr.so inst-amarisoftenb/
cp ${base}/inst-tmp/trx_sdr-linux-2021-03-15/libc_wrapper_sdr.so inst-amarisoftenb/

# Copy the uhd library and create the tarball.
cp ${base}/inst-tmp/trx_uhd-linux-2021-03-15/trx_uhd.so inst-amarisoftenb/
this="amarisoftenb.build-${BUILD_NUMBER-$(date +%Y-%m-%d_%H_%M_%S)}"
tar="${this}.tgz"
tar -czf "$tar" -C inst-amarisoftenb/ .
md5sum "$tar" > "${this}.md5"

# Create amarisoftue inst:
if [ "x${HAVE_AMARISOFT_LTEUE}" = "x1" ]; then
        rm -rf inst-amarisoftue && mkdir inst-amarisoftue || exit 1
        tar --strip-components=1 -zxf inst-tmp/*/lteue-linux-2018-10-18.tar.gz -C inst-amarisoftue/
        if [ "x${BUILD_AMARISOFT_TRX_ZMQ}" = "x1" ]; then
                cp ${base}/${project_name_srslte}/build/lib/src/phy/rf/libsrsran_rf.so inst-amarisoftue/
                cp ${base}/${project_name_zmq}/build/libtrx_zmq-linux-2018-10-18.so inst-amarisoftue/trx_zmq.so
                patchelf --set-rpath '$ORIGIN/' inst-amarisoftue/trx_zmq.so
                cd inst-amarisoftue && ln -s libsrsran_rf.so libsrsran_rf.so.0 && cd ..
        fi
        cp ${base}/inst-tmp/trx_uhd-linux-2018-10-18/trx_uhd.so inst-amarisoftue/
        this="amarisoftue.build-${BUILD_NUMBER-$(date +%Y-%m-%d_%H_%M_%S)}"
        tar="${this}.tgz"
        tar -czf "$tar" -C inst-amarisoftue/ .
        md5sum "$tar" > "${this}.md5"
fi

# Create amarisoftepc inst:
rm -rf inst-amarisoftepc && mkdir inst-amarisoftepc || exit 1
tar --strip-components=1 -zxf inst-tmp/*/ltemme-linux*.tar.gz -C inst-amarisoftepc/

# place newer libssl-1.1 and libcrypto-1.1 for older OS distributions inside the EPC folder
cp inst-tmp/*/libs/libssl* inst-amarisoftepc/
cp inst-tmp/*/libs/libcrypto* inst-amarisoftepc/

# Copy ltesim_server from UE package if available
if [ "x${HAVE_AMARISOFT_LTEUE}" = "x1" ]; then
        # Untar newer lteue version for fresh ltesim_server (2018 uses libssl-1.0.0)
        rm -rf inst-amarisoftue && mkdir inst-amarisoftue || exit 1
        tar --strip-components=1 -zxf inst-tmp/*/lteue-linux-2021-03-15.tar.gz -C inst-amarisoftue/
        cp inst-amarisoftue/ltesim_server inst-amarisoftepc/
fi
this="amarisoftepc.build-${BUILD_NUMBER-$(date +%Y-%m-%d_%H_%M_%S)}"
tar="${this}.tgz"
tar -czf "$tar" -C inst-amarisoftepc/ .
md5sum "$tar" > "${this}.md5"
