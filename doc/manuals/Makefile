OSMO_GSM_MANUALS_DIR := $(shell ./osmo-gsm-manuals-dir.sh)
srcdir=$(CURDIR)

ASCIIDOC = osmo-gsm-tester-manual.adoc
ASCIIDOC_DEPS = $(srcdir)/chapters/*.adoc
include $(OSMO_GSM_MANUALS_DIR)/build/Makefile.asciidoc.inc

include $(OSMO_GSM_MANUALS_DIR)/build/Makefile.common.inc
