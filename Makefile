all: deps version check

.PHONY: version check

deps:
	./check_dependencies.py

version:
	./update_version.sh

check:
	$(MAKE) -C test check	
	@echo "make check: success"

# vim: noexpandtab tabstop=8 shiftwidth=8
