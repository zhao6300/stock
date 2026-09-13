.PHONY: install unit integration test run start clean

export PYTHONPATH ?= src

install:
	./install.sh

unit:
	pytest -q tests/test_indicators.py tests/test_models.py tests/test_data.py

integration:
	pytest -q tests/test_api.py tests/test_auth.py tests/test_analysis_flow.py tests/test_import.py tests/test_saved_filters.py

test: unit integration

run:
	PYTHONPATH=src uvicorn a_stock_platform.app:app --reload --host 0.0.0.0 --port 8000

start:
	./start.sh

start80:
	HOST=0.0.0.0 PORT=80 ./start.sh

clean:
	rm -rf .pytest_cache src/*.egg-info || true
