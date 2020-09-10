rem Windows batch file to run coverage tests before contributing

@echo off

cd /d "%~dp0"

coverage run -m pytest -v
if %errorlevel% NEQ 0 pause
coverage report -m
coverage html
start "" htmlcov\index.html
