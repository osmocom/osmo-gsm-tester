About Osmo-GSM-Tester
=====================

Osmo-GSM-Tester is a software to run automated tests on real hardware, initially
foremost to verify that ongoing Osmocom software development continues to work
with various BTS models, while being flexibly configurable and extendable to
work for other technologies, setups and projects. It can nowadays also be used
to run 4G networks with components from different providers.

Find Osmo-GSM-Tester issue tracker and wiki online at
https://osmocom.org/projects/osmo-gsm-tester

Simple configuration setups can be found under _doc/examples/_ directory. A
Osmocom's public Osmo-Gsm-Tester configuration setup is also maintained here
under _sysmocom/_ as a reference for others.

Ansible scripts to set up hosts to be used as Osmo-GSM-Tester Main Units or/and
Slave Units on the above mentioned setup can be found at
https://gitea.osmocom.org/osmocom/osmo-ci/src/branch/master/ansible, which
actually install sample system configuration files from _utils/_ directory in
this same repository.

A sample Docker setup is also maintained publicly at
https://gitea.osmocom.org/osmocom/docker-playground/src/branch/master/osmo-gsm-tester.

For the complete documentation, please refer to Osmo-GSM-Tester User manual,
available in sources under _doc/manuals/_ under this same repository, and
prebuilt in pdf form at
http://ftp.osmocom.org/docs/latest/osmo-gsm-tester-manual.pdf
