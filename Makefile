all: deps version check manual

.PHONY: version check

deps:
	./contrib/check_dependencies.py

version:
	./contrib/update_version.sh

manual:
	$(MAKE) -C doc/manuals

check:
	$(MAKE) -C selftest check
	@echo "make check: success"

clean:
	$(MAKE) -C selftest clean
	$(MAKE) -C doc/manuals clean
	@find . -name "*__pycache__" -type d -print0 | xargs -0 rm -rvf
	@rm -fv ./src/osmo_gsm_tester/_version.py
	@rm -fv ./version
# vim: noexpandtab tabstop=8 shiftwidth=8
