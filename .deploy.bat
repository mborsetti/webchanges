REM Windows batch file to deploy new release

@echo off
set "project=%~dp0"
set "project=%project:~0,-1%"
set "project=%project:\=" & set "project=%"

title Deploy new release of '%project%' project

echo Deploy new release of '%project%' project
echo ==========================================
echo.
set /p r=Did you run local tests (tox)? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Did you update CHANGELOG.rst by adding today's date under `Unreleased`? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p v=Do you want to bump by a major, minor or patch version? [PATCH] || set v=patch
echo.
bump2version --verbose --allow-dirty --dry-run --commit --tag --no-sign-tags %v%
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)

set /p r=Do you want to do it for real? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b

echo.
echo bumping version to next %v%
bump2version --commit --tag --no-sign-tags %v%
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)

echo.
echo pushing branch
git push
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)

echo.
echo pushing branch to main and setting flags
git push origin unreleased:main --follow-tags
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)

echo.
echo bumping version locally to post
bump2version --no-commit --no-tag postkind
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)

echo Remember to create a new section in CHANGELOG.rst as follows:
echo `Unreleased`
echo ===============

pause
exit
