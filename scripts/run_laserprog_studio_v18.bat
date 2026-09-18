@echo off
setlocal
REM Compatibility wrapper kept for older shortcuts.
call "%~dp0run_laserprog_studio.bat" %*
set "LAUNCH_EXIT=%ERRORLEVEL%"
endlocal & exit /b %LAUNCH_EXIT%
