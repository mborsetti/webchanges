rem Windows script to run all tests; run prior to contributing
@echo off

pip install -U -r requirements.txt
if not errorlevel 0 pause
pip install -U -r requirements_testing.txt
if not errorlevel 0 pause
pre-commit autoupdate
if not errorlevel 0 pause
pre-commit run -a
if not errorlevel 0 pause
python -m pytest -v
if not errorlevel 0 pause
