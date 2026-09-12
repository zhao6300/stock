.PHONY: install unit integration test run clean

install:
	python -m pip install -r requirements.txt

unit:
	pytest -q tests/test_indicators.py tests/test_models.py tests/test_data.py

integration:
	pytest -q tests/test_api.py tests/test_auth.py tests/test_analysis_flow.py

test: unit integration

run:
	PYTHONPATH=src uvicorn a_stock_platform.app:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf .pytest_cache src/*.egg-info || true
