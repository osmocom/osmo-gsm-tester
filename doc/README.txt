DOCUMENTATION

For the complete documentation, please refer to the osmo-gsm-manuals:
http://git.osmocom.org/osmo-gsm-manuals/
http://jenkins.osmocom.org/jenkins/job/Osmocom_Manuals/ws/


INSTALLATION

So far the osmo-gsm-tester directory is manually placed in /usr/local/src


DEPENDENCIES

Packages required to run the osmo-gsm-tester:

  apt-get install \
  dbus \
  tcpdump \
  sqlite3 \
  python3 \
  python3-yaml \
  python3-mako \
  python3-gi \
  ofono \
  python3-pip \
  python3-usb
  pip3 install git+git://github.com/podshumok/python-smpplib.git
  pip3 install pydbus
  pip3 install pysispm

To build ofono:
  apt-get install libglib2.0-dev \
		  libdbus-1-dev \
		  libudev-dev \
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


Jenkins Configuration

(TODO: jenkins build slave details)

When adding an entry to jenkins' known_hosts file, be aware that you need to
add an actual RSA host key. Using 'ssh' to access the main unit may work, but
jenkins will still fail to access it in the absence of a full RSA host key:

  ssh-keyscan -H $my_main_unit_ip_addr >> ~jenkins/.ssh/known_hosts


LAUNCHING A TEST RUN

osmo-gsm-tester watches /var/tmp/osmo-gsm-tester for instructions to launch
test runs.  A test run is triggered by a subdirectory containing binaries and a
checksums file, typically created by jenkins using the scripts in contrib/.
