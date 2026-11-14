# One command reproduces every number from the raw PhysioNet files.
# Runtime on a 2-core, 8 GB machine: about 17 minutes after the data is downloaded.

PY ?= python3

.PHONY: reproduce data audit train evaluate secondary artifacts test app

reproduce: audit train evaluate secondary artifacts test

data:
	$(PY) scripts/01_audit.py --download

audit:
	$(PY) scripts/01_audit.py

train:
	$(PY) scripts/02_train.py

evaluate:
	$(PY) scripts/03_evaluate.py

secondary:
	$(PY) scripts/04_secondary.py

artifacts:
	$(PY) scripts/05_app_artifacts.py

test:
	$(PY) -m pytest -q tests

app:
	$(PY) app/app.py
