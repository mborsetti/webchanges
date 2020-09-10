rem Windows batch file to run tests and coverage before contributing

@echo off

cd /d "%~dp0"

coverage run -m pytest -v
if %errorlevel% NEQ 0 pause
coverage report -m
coverage html
start "" htmlcov\index.html
