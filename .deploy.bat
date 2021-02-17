REM Windows batch file to deploy new release

@echo off
set "project=%~dp0"
set "project=%project:~0,-1%"
set "project=%project:\=" & set "project=%"

title Deploy new release of '%project%' project

echo Deploy new release of '%project%' project
echo ==========================================
echo.
set /p r=Did you update CHANGELOG.rst by adding today's date under `Unreleased`? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Did you copy the release info from CHANGELOG.rst to RELEASE.rst? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Did you run local tests (tox) and commit? [N/y] || set r=n
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
bump2version --allow-dirty --commit --tag --no-sign-tags %v%
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)
rem
rem echo.
rem echo pushing branch
rem git push
rem if NOT ["%errorlevel%"]==["0"] (
rem     pause
rem     exit /b %errorlevel%
rem )

echo.
echo Pushing branch to main and setting release tag
git push origin unreleased:main --follow-tags
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)

echo.
echo Bumping version locally to post-release 0 (will complain about CHANGELOG.rst)
bump2version --no-commit --no-tag postkind
if NOT ["%errorlevel%"]==["0"] (
    pause
)

echo Remember to create a new section in CHANGELOG.rst as follows:
echo `Unreleased`
echo =================

pause
exit
