# One command reproduces every number from the raw PhysioNet files.
# Runtime on a 2-core, 8 GB machine: several hours, almost all of it the three
# temporal GRU seeds (`make deep`); everything else takes about 25 minutes.

PY ?= python3

.PHONY: reproduce data audit train deep robust-candidates robust-gate familiarity blend ensemble gru-ensemble final-mix web evaluate compare secondary artifacts bundle external-audit test app api

reproduce: audit train deep familiarity blend ensemble gru-ensemble final-mix evaluate compare secondary artifacts bundle web test

data:
	$(PY) scripts/01_audit.py --download

audit:
	$(PY) scripts/01_audit.py

train:
	$(PY) scripts/02_train.py

deep:
	$(PY) scripts/08_temporal_gru.py
	$(PY) scripts/08_temporal_gru.py --seed 2027
	$(PY) scripts/08_temporal_gru.py --seed 2028

# Exploratory candidates. They never overwrite the baseline GRU; run the
# validation-only gate before any held-out evaluation.
robust-candidates:
	$(PY) scripts/08_temporal_gru.py --input-mode values_only --target-window early_6_12 --name gru_early_values
	$(PY) scripts/08_temporal_gru.py --input-mode masked --target-window early_6_12 --measurement-dropout 0.15 --name gru_early_maskdrop

robust-gate:
	$(PY) scripts/17_candidate_gate.py --candidates temporal_gru,gru_early_values,gru_early_maskdrop

familiarity:
	$(PY) scripts/07_familiarity_guard.py

blend:
	$(PY) scripts/10_blend.py

ensemble:
	$(PY) scripts/09_validated_ensemble.py

gru-ensemble:
	$(PY) scripts/12_gru_ensemble.py

final-mix:
	$(PY) scripts/15_final_mix.py

web:
	$(PY) scripts/13_web_export.py
	$(PY) scripts/16_lite_model.py

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
