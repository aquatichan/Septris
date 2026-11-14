# One command reproduces every number from the raw PhysioNet files.
# Runtime on a 2-core, 8 GB machine: about 17 minutes after the data is downloaded.

PY ?= python3

.PHONY: reproduce data audit train deep blend ensemble evaluate compare secondary artifacts bundle external-audit test app api

reproduce: audit train deep blend ensemble evaluate compare secondary artifacts bundle test

data:
	$(PY) scripts/01_audit.py --download

audit:
	$(PY) scripts/01_audit.py

train:
	$(PY) scripts/02_train.py

deep:
	$(PY) scripts/08_temporal_gru.py

blend:
	$(PY) scripts/10_blend.py

ensemble:
	$(PY) scripts/14_validated_ensemble.py

compare:
	$(PY) scripts/11_compare_models.py

evaluate:
	$(PY) scripts/03_evaluate.py

secondary:
	$(PY) scripts/04_secondary.py

artifacts:
	$(PY) scripts/05_app_artifacts.py

bundle:
	$(PY) scripts/11_export_model_bundle.py

external-audit:
	@test -n "$(SOURCE)" && test -n "$(INPUT)" && test -n "$(REPORT)" || (echo "Use SOURCE=eicu|mimiciv|hirid INPUT=/secure/hourly.parquet REPORT=outputs/external/audit.json"; exit 2)
	$(PY) scripts/12_external_audit.py --source $(SOURCE) --input $(INPUT) --report $(REPORT)

test:
	$(PY) -m pytest -q tests

app:
	$(PY) app/app.py

api:
	uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
