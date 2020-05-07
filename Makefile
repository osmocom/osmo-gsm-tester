all: deps version check manual

.PHONY: version check

deps:
	./check_dependencies.py

version:
	./update_version.sh

manual:
	$(MAKE) -C doc/manuals

check:
	$(MAKE) -C selftest check
	@echo "make check: success"

# vim: noexpandtab tabstop=8 shiftwidth=8
