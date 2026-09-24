PYTHON ?= python3

.PHONY: all plots tables
all plots tables:
	$(PYTHON) reproduce.py $@
