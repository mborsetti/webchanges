@echo off

REM Windows batch file to deploy new release

REM Always work from the unreleased branch:
REM 1) create a rc and push (upload) it. Ensure CI works
REM 2) update bumpversion.cfg to ensure that it has the correct substitution bits
REM 3) run this file!

set "project=%~dp0"
set "project=%project:~0,-1%"
set "project=%project:\=" & set "project=%"

title Deploy new release of '%project%' project

echo Deploy new release of '%project%' project
echo ==========================================
echo.
set /p r=Did you run local tests (tox) and commit to unreleased? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Are you in the unreleased branch? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Did you update CHANGELOG.rst by adding today's date under `Unreleased`? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Did you copy the release info from CHANGELOG.rst to RELEASE.rst? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p v=Do you want to bump by a major, minor or patch version? [minor] || set v=minor
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
echo Bumping version to next %v%
bump2version --commit --tag --no-sign-tags %v%
if NOT ["%errorlevel%"]==["0"] (
    echo make sure to commit all files (other than those modified by bump2version)
    echo before running this script
    pause
    exit /b %errorlevel%
)

echo.
echo Pushing branch to main and setting release tag
git push origin unreleased:main --follow-tags
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)

echo.
echo Bumping version locally to post-release
bump2version --no-commit --no-tag postkind
if NOT ["%errorlevel%"]==["0"] (
    pause
)

echo.
echo Remember to fix CHANGELOG.rst version headers
echo (reinsert release one, which was just overwritten)

pause
exit
