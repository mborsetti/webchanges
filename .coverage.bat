@echo off
rem Windows batch file to run tests and coverage before contributing

cd /d "%~dp0"

coverage run -m pytest -v
if %errorlevel% NEQ 0 pause
coverage html
start "" htmlcov\index.html
