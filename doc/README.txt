INSTALLATION

So far the osmo-gsm-tester directory is manually placed in /usr/local/src


DEPENDENCIES

Packages required to run the osmo-gsm-tester:

  dbus
  python3
  python3-dbus
  python3-pip
  python3-mako
  tcpdump
  smpplib (pip install git+git://github.com/podshumok/python-smpplib.git)
  ofono

To build ofono:
  libglib2.0-dev
  libdbus-1-dev
  libudev-dev
  mobile-broadband-provider-info


INSTALLATION

Place a copy of the osmo-gsm-tester repository in /usr/local/src/

  cp install/osmo-gsm-tester-limits.conf /etc/security/limits.d/
  cp install/*.service /lib/systemd/system/
  cp install/org.ofono.conf /etc/dbus-1/system.d/
  systemctl daemon-reload

To run:

  systemctl enable ofono
  systemctl start ofono
  systemctl status ofono

  systemctl enable osmo-gsm-tester
  systemctl start osmo-gsm-tester
  systemctl status osmo-gsm-tester


To stop:

  systemctl stop osmo-gsm-tester

After ofonod has been started and modems have been connected to the system,
you can run the 'list-modems' script located in /usr/local/src/ofono/test to get
a list of the modems that have been detected by ofono.


CONFIGURATION

Host System configuration

Create the /var/tmp/osmo-gsm-tester directory. It will be used to accept new test jobs.

Test resources (NITB, BTS and modems) are currently configured in the test_manager.py.

For every nitb resource that can be allocated, one alias IP address needs
to be set up in /etc/network/interfaces on the interface that is connected to the BTSes.
By add the following lines for each nitb instance that can be allocated (while making
sure each interface alias and IP is unique)

  auto eth1:0
  allow-hotplug eth1:0
  iface eth1:0 inet static
	address 10.42.42.2
	netmask 255.255.255.0

Also make sure, the user executing the tester is allowed to run tcpdump.  If
the user is not root, we have used the folloing line to get proper permissions:

  groupadd pcap
  addgroup <your-user-name> pcap
  setcap cap_net_raw,cap_net_admin=eip /usr/sbin/tcpdump
  chgroup pcap /usr/sbin/tcpdump
  chmod 0750 /usr/sbin/tcpdump

The tester main unit must be able to ssh without password to the sysmobts (and
possibly other) hardware: place the main unit's public SSH key on the sysmoBTS.
Log in via SSH at least once to accept the BTS' host key.


LAUNCHING A TEST RUN

osmo-gsm-tester watches /var/tmp/osmo-gsm-tester for instructions to launch
test runs.  A test run is triggered by a subdirectory containing binaries and a
checksums file, typically created by jenkins using the scripts in contrib/.
