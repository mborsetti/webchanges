@echo off
chcp 65001 >NUL

REM Windows batch file to deploy new release

REM To deploy (always work from the unreleased branch):
REM 1) create a rc version (e.g. bump2version prekind)
REM 2) push (upload) it. Ensure CI works
REM 3) update bumpversion.cfg to ensure that it has the correct substitution bits
REM 4) run this file!

REM To bump version from x.x.x.rc0 onwards:
REM > bump2version --verbose --allow-dirty --no-commit --no-tag pre --dry-run

REM For manual release in PyCharm:
REM 1) Commit the release; comment is 'Release x.x'
REM 2) In PyCharm Git (ALT+F9) -> Log, right click on the release and select New Tag. Enter tag in format vx.x
REM 3) > git push origin unreleased:main --tags

set "project=%~dp0"
set "project=%project:~0,-1%"
set "project=%project:\=" & set "project=%"

title Deploy new release of '%project%' project

echo Deploy new release of '%project%' project
echo ==========================================
echo.
set /p r=Did you copy the release info from CHANGELOG.rst to RELEASE.rst, updated migration.rst, and updated ^
  WISHLIST.rst? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Did you update CHANGELOG.rst by replacing 'Unreleased' with today's date`? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Did you run local tests (tox) and ensure CI passed? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Did you check https://readthedocs.org/projects/webchanges/builds/ and ensure docs built there? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Are you in the unreleased branch? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p r=Did you commit all files (other than those that will be modified by bump2version)? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b
set /p v=Do you want to bump by prekind (i.e. from rc → released) or major, minor or patch version? [prekind] || set ^
  v=prekind
echo.
bump2version --verbose --dry-run --commit --tag --no-sign-tags %v%
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)

set /p r=Do you want to do it for real? [N/y] || set r=n
if %r% EQU N r=n
if %r% EQU n exit /b

echo.
echo Bumping version to next %v%; this will also commit the changes.
echo.
bump2version --commit --tag --no-sign-tags %v%

pause

echo.
echo Pushing branch to main including release tag
git push origin unreleased:main --tags
if NOT ["%errorlevel%"]==["0"] (
    pause
    exit /b %errorlevel%
)

echo.
echo Bumping version locally to post-release
bump2version --verbose --no-commit --no-tag postkind
if NOT ["%errorlevel%"]==["0"] (
    pause
)

echo.
echo Remember to fix CHANGELOG.rst version headers
echo (reinsert release one, which was just overwritten)

pause
exit
