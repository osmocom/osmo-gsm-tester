SETTING UP sysmobts

PACKAGE VERSIONS

Depending on the code to be tested, select the stable, testing or nightly opkg
feed:

To change the feed and packages installed on the sysmobts edit the
following files in /etc/opkg/

* all-feed.conf
* armv5te-feed.conf
* sysmobts-v2-feed.conf

and adjust the URL. For example, to move to the testing feeds:

  sed -i 's/201310/201310-testing/g' /etc/opkg/*.conf

Then run 'opkg update', 'opkg upgrade' and finally 'reboot'.


DISABLE SERVICES

To use the sysmobts together with the tester, the following systemd services must be disabled
but using the mask and not using the disable option. You can use the following lines:

systemctl mask osmo-nitb
systemctl mask sysmobts
systemctl mask sysmobts-mgr


SSH ACCESS

Copy the SSH public key from the system/user that runs the tester to the BTS
authorized keys file so the tester will be able to deploy binaries.

  scp my_key.pub $sysmobts:
  ssh $sysmobts
  cat my_key.pub >> ~/.ssh/authorized_keys

It is also advisable to configure the eth0 network interface of the BTS to a
static IP address instead of using DHCP. To do so adjust /etc/network/interfaces
and change the line

  iface eth0 inet dhcp

to

  iface eth0 inet static
  	address 10.42.42.114
  	netmask 255.255.255.0
  	gateway 10.42.42.1

Set the name server in /etc/resolve.conf (most likely to the IP of the
gateway).


ALLOW CORE FILES

In case a binary run for the test crashes, we allow it to write a core file, to
be able to analyze the crash later. This requires a limit rule:

  scp install/osmo-gsm-tester-limits.conf sysmobts:/etc/security/limits.d/
